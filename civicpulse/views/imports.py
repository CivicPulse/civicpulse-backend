"""
Import views for CivicPulse application.

This module provides functionality to import data into the application
with proper audit logging and error handling.
"""

import csv
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from civicpulse.middleware.audit import get_request_audit_context
from civicpulse.models import VALID_US_STATE_CODES, Person, VoterRecord
from civicpulse.signals import log_data_import

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser as User
else:
    User = get_user_model()

logger = logging.getLogger(__name__)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("civicpulse.add_person", raise_exception=True), name="dispatch"
)
class PersonImportView(View):
    """
    View for importing Person data from CSV format.

    Provides both GET (form display) and POST (file processing) functionality
    with comprehensive error handling and audit logging.
    """

    template_name = "civicpulse/import_persons.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        """
        Display the import form.

        Returns:
            HttpResponse with the import form template
        """
        context = {
            "title": "Import Persons",
            "expected_headers": self._get_expected_headers(),
            "help_text": self._get_help_text(),
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        """
        Process uploaded CSV file and import persons.

        Args:
            request: The HTTP request with uploaded file

        Returns:
            HttpResponse with results or form with errors
        """
        if "csv_file" not in request.FILES:
            messages.error(request, "Please select a CSV file to upload.")
            return self.get(request)

        csv_file = request.FILES["csv_file"]

        # Validate file (ensure it's a single uploaded file)
        filename = getattr(csv_file, "name", None)
        if not filename or not filename.endswith(".csv"):
            messages.error(request, "Please upload a CSV file (.csv extension).")
            return self.get(request)

        # Get configured file size limit
        max_file_size = getattr(
            settings, "PERSON_IMPORT_MAX_FILE_SIZE", 10 * 1024 * 1024
        )
        try:
            # Handle invalid setting values gracefully
            if not isinstance(max_file_size, int | float) or max_file_size <= 0:
                max_file_size = 10 * 1024 * 1024  # Fallback to 10MB
        except TypeError:
            max_file_size = 10 * 1024 * 1024  # Fallback to 10MB

        if (
            hasattr(csv_file, "size")
            and csv_file.size
            and csv_file.size > max_file_size
        ):
            # Convert bytes to human-readable format
            max_size_mb = max_file_size / (1024 * 1024)
            messages.error(
                request, f"File size too large. Maximum size is {max_size_mb:.0f}MB."
            )
            return self.get(request)

        try:
            # Process the CSV file
            results = self._process_csv_file(csv_file, request.user)

            # Get audit context
            audit_context = get_request_audit_context(request)

            # Log the import operation
            log_data_import(
                user=cast(Any, request.user),
                import_type="persons",
                record_count=results["imported_count"],
                filename=getattr(csv_file, "name", "unknown"),
                ip_address=audit_context.get("ip_address"),
                user_agent=audit_context.get("user_agent"),
                errors_count=len(results["errors"]),
                duplicate_count=results["duplicate_count"],
            )

            # Show results to user
            if results["imported_count"] > 0:
                messages.success(
                    request,
                    f"Successfully imported {results['imported_count']} persons.",
                )

            if results["duplicate_count"] > 0:
                messages.warning(
                    request, f"Skipped {results['duplicate_count']} duplicate records."
                )

            if results["errors"]:
                messages.error(
                    request,
                    f"Failed to import {len(results['errors'])} records. "
                    "See details below.",
                )

            context = {
                "title": "Import Results",
                "results": results,
                "expected_headers": self._get_expected_headers(),
                "help_text": self._get_help_text(),
            }
            return render(request, self.template_name, context)

        except Exception as e:
            logger.error(f"Error during person import: {e}", exc_info=True)
            messages.error(
                request,
                "An error occurred during import. Please check your file format "
                "and try again.",
            )
            return self.get(request)

    def _process_csv_file(self, csv_file, user) -> dict[str, Any]:
        """
        Process the uploaded CSV file and import persons.

        Args:
            csv_file: The uploaded CSV file
            user: The user performing the import

        Returns:
            Dictionary with import results
        """
        results = {
            "imported_count": 0,
            "duplicate_count": 0,
            "errors": [],
            "filename": csv_file.name,
        }

        # Read and decode CSV file
        file_content = csv_file.read().decode("utf-8")
        csv_reader = csv.DictReader(file_content.splitlines())

        # Validate headers
        actual_headers = set(csv_reader.fieldnames or [])

        # Check for required headers
        required_headers = {"First Name", "Last Name"}
        missing_required = required_headers - actual_headers
        if missing_required:
            raise ValidationError(
                f"Missing required headers: {', '.join(missing_required)}"
            )

        # Process each row
        with transaction.atomic():
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for header
                try:
                    person_data, voter_data = self._parse_csv_row(row)

                    # Check for duplicates
                    if self._is_duplicate_person(person_data):
                        results["duplicate_count"] += 1
                        continue

                    # Create person
                    person = Person(**person_data, created_by=user)
                    person.full_clean()
                    person.save()

                    # Create voter record if data provided
                    if voter_data.get("voter_id"):
                        voter_record = VoterRecord(**voter_data, person=person)
                        voter_record.full_clean()
                        voter_record.save()

                    results["imported_count"] += 1

                except ValidationError as e:
                    error_msg = f"Row {row_num}: {self._format_validation_error(e)}"
                    results["errors"].append(error_msg)

                except Exception as e:
                    error_msg = f"Row {row_num}: Unexpected error - {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(f"Import error on row {row_num}: {e}", exc_info=True)

        return results

    def _parse_csv_row(
        self, row: dict[str, str]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Parse a CSV row into person and voter record data.

        Args:
            row: Dictionary representing a CSV row

        Returns:
            Tuple of (person_data, voter_data) dictionaries
        """
        person_data: dict[str, Any] = {}
        voter_data: dict[str, Any] = {}

        # Person fields
        person_data["first_name"] = row.get("First Name", "").strip()
        person_data["middle_name"] = row.get("Middle Name", "").strip()
        person_data["last_name"] = row.get("Last Name", "").strip()
        person_data["suffix"] = row.get("Suffix", "").strip()

        # Date of birth
        dob_str = row.get("Date of Birth", "").strip()
        if dob_str:
            try:
                person_data["date_of_birth"] = datetime.strptime(
                    dob_str, "%Y-%m-%d"
                ).date()
            except ValueError:
                # Try alternative formats
                for fmt in ["%m/%d/%Y", "%m-%d-%Y"]:
                    try:
                        person_data["date_of_birth"] = datetime.strptime(
                            dob_str, fmt
                        ).date()
                        break
                    except ValueError:
                        continue

        # Gender
        gender_str = row.get("Gender", "").strip().upper()
        gender_map = {
            "MALE": "M",
            "FEMALE": "F",
            "OTHER": "O",
            "M": "M",
            "F": "F",
            "O": "O",
        }
        person_data["gender"] = gender_map.get(gender_str, "U")

        # Contact information
        person_data["email"] = row.get("Email", "").strip()
        person_data["phone_primary"] = row.get("Phone Primary", "").strip()
        person_data["phone_secondary"] = row.get("Phone Secondary", "").strip()

        # Address information
        person_data["street_address"] = row.get("Street Address", "").strip()
        person_data["apartment_number"] = row.get("Apartment Number", "").strip()
        person_data["city"] = row.get("City", "").strip()
        person_data["state"] = row.get("State", "").strip().upper()
        person_data["zip_code"] = row.get("ZIP Code", "").strip()
        person_data["county"] = row.get("County", "").strip()

        # Additional information
        person_data["occupation"] = row.get("Occupation", "").strip()
        person_data["employer"] = row.get("Employer", "").strip()

        # Voter record fields
        voter_data["voter_id"] = row.get("Voter ID", "").strip()

        # Registration status
        reg_status = row.get("Registration Status", "").strip().lower()
        status_map = {
            "active": "active",
            "inactive": "inactive",
            "pending": "pending",
            "cancelled": "cancelled",
            "suspended": "suspended",
        }
        voter_data["registration_status"] = status_map.get(reg_status, "active")

        # Party affiliation
        party = row.get("Party Affiliation", "").strip().upper()
        party_map = {
            "DEMOCRATIC": "DEM",
            "DEMOCRAT": "DEM",
            "DEM": "DEM",
            "REPUBLICAN": "REP",
            "REP": "REP",
            "INDEPENDENT": "IND",
            "IND": "IND",
            "GREEN": "GRN",
            "LIBERTARIAN": "LIB",
            "LIB": "LIB",
            "OTHER": "OTH",
            "NO PARTY": "NON",
            "NONE": "NON",
        }
        voter_data["party_affiliation"] = party_map.get(party, "NON")

        # Voter score
        score_str = row.get("Voter Score", "").strip()
        if score_str:
            try:
                voter_data["voter_score"] = int(score_str)
            except ValueError:
                voter_data["voter_score"] = 0

        # Last voted date
        last_voted_str = row.get("Last Voted Date", "").strip()
        if last_voted_str:
            try:
                voter_data["last_voted_date"] = datetime.strptime(
                    last_voted_str, "%Y-%m-%d"
                ).date()
            except ValueError:
                # Try alternative formats
                for fmt in ["%m/%d/%Y", "%m-%d-%Y"]:
                    try:
                        voter_data["last_voted_date"] = datetime.strptime(
                            last_voted_str, fmt
                        ).date()
                        break
                    except ValueError:
                        continue

        return person_data, voter_data

    def _is_duplicate_person(self, person_data: dict[str, Any]) -> bool:
        """
        Check if a person with the same data already exists using efficient
        QuerySet operations.

        Args:
            person_data: Dictionary of person data

        Returns:
            True if duplicate exists, False otherwise
        """
        return self._check_duplicate_efficient(person_data)

    def _check_duplicate_efficient(self, person_data: dict[str, Any]) -> bool:
        """
        Efficiently check for duplicate persons using database queries without
        creating temporary instances.

        This method replicates the logic from Person.get_potential_duplicates()
        but without instantiating temporary Person objects, making it much more
        efficient for large imports.

        Args:
            person_data: Dictionary of person data to check for duplicates

        Returns:
            True if duplicate exists, False otherwise
        """
        filters = Q()

        # Extract values safely with defaults
        first_name = person_data.get("first_name", "").strip()
        last_name = person_data.get("last_name", "").strip()
        date_of_birth = person_data.get("date_of_birth")
        email = person_data.get("email", "").strip()
        phone_primary = person_data.get("phone_primary", "").strip()
        phone_secondary = person_data.get("phone_secondary", "").strip()
        street_address = person_data.get("street_address", "").strip()
        zip_code = person_data.get("zip_code", "").strip()

        # Same name and DOB - highest priority duplicate detection
        if first_name and last_name and date_of_birth:
            filters |= Q(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                date_of_birth=date_of_birth,
            )

        # Same email (if provided and not empty)
        if email:
            filters |= Q(email__iexact=email)

        # Same primary phone (if provided and not empty)
        if phone_primary:
            filters |= Q(phone_primary=phone_primary)

        # Same secondary phone (if provided and not empty)
        if phone_secondary:
            filters |= Q(phone_secondary=phone_secondary)

        # Same name and address (if all required fields provided)
        if first_name and last_name and street_address and zip_code:
            filters |= Q(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                street_address__iexact=street_address,
                zip_code=zip_code,
            )

        # If no meaningful criteria for duplicate detection, return False
        if not filters:
            return False

        # Use select_related to optimize queries and only check active persons
        return Person.objects.filter(filters).exists()

    def _format_validation_error(self, error: ValidationError) -> str:
        """
        Format validation error for display.

        Args:
            error: The ValidationError

        Returns:
            Formatted error message
        """
        if hasattr(error, "message_dict"):
            # Field-specific errors
            messages = []
            for field, errors in error.message_dict.items():
                field_errors = ", ".join(errors)
                messages.append(f"{field}: {field_errors}")
            return "; ".join(messages)
        else:
            # General error
            return str(error)

    def _get_expected_headers(self) -> list[str]:
        """
        Get the list of expected CSV headers.

        Returns:
            List of header names
        """
        return [
            "First Name",  # Required
            "Middle Name",
            "Last Name",  # Required
            "Suffix",
            "Date of Birth",
            "Gender",
            "Email",
            "Phone Primary",
            "Phone Secondary",
            "Street Address",
            "Apartment Number",
            "City",
            "State",
            "ZIP Code",
            "County",
            "Occupation",
            "Employer",
            "Voter ID",
            "Registration Status",
            "Party Affiliation",
            "Voter Score",
            "Last Voted Date",
        ]

    def _get_help_text(self) -> dict[str, str]:
        """
        Get help text for various fields.

        Returns:
            Dictionary of field help text
        """
        # Get configured file size limit and convert to MB
        max_file_size = getattr(
            settings, "PERSON_IMPORT_MAX_FILE_SIZE", 10 * 1024 * 1024
        )
        try:
            # Handle invalid setting values gracefully
            if not isinstance(max_file_size, int | float) or max_file_size <= 0:
                max_file_size = 10 * 1024 * 1024  # Fallback to 10MB
            max_size_mb = max_file_size / (1024 * 1024)
            # Round up for display (e.g., 0.5MB shows as 1MB)
            max_size_mb_display = (
                int(max_size_mb)
                if max_size_mb == int(max_size_mb)
                else int(max_size_mb) + 1
            )
        except (TypeError, ZeroDivisionError):
            # Fallback for any arithmetic errors
            max_size_mb_display = 10

        return {
            "required_fields": "First Name and Last Name are required fields.",
            "date_formats": (
                "Date fields accept YYYY-MM-DD, MM/DD/YYYY, or MM-DD-YYYY formats."
            ),
            "gender_values": (
                "Gender: Male/M, Female/F, Other/O, or leave blank for Unknown."
            ),
            "state_codes": (
                f"State: Use 2-letter codes "
                f"({', '.join(VALID_US_STATE_CODES[:10])}...)."
            ),
            "party_codes": (
                "Party: Democratic/DEM, Republican/REP, Independent/IND, etc."
            ),
            "voter_score": (
                "Voter Score: Number between 0-100 indicating voting frequency."
            ),
            "file_limits": (
                f"File size limit: {max_size_mb_display}MB. Duplicates will be skipped."
            ),
        }
