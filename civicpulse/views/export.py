"""
Export views for CivicPulse application.

This module provides functionality to export data from the application
with proper audit logging.
"""

import csv
import logging
from typing import Any

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from civicpulse.middleware.audit import get_request_audit_context
from civicpulse.models import Person
from civicpulse.signals import log_data_export

logger = logging.getLogger(__name__)


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("civicpulse.view_person", raise_exception=True), name="dispatch"
)
class PersonExportView(View):
    """
    View for exporting Person data to CSV format.

    Supports filtering by various criteria and logs all export operations
    for audit purposes.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        """
        Export persons to CSV format.

        Query parameters:
        - state: Filter by state code (e.g., 'CA', 'NY')
        - zip_code: Filter by ZIP code
        - min_age: Minimum age filter
        - max_age: Maximum age filter
        - registration_status: Voter registration status
        - party_affiliation: Party affiliation
        - format: Export format (defaults to 'csv')

        Returns:
            HttpResponse with CSV data
        """
        try:
            # Get query parameters for filtering
            filters = self._get_filters(request)
            export_format = request.GET.get("format", "csv").lower()

            # Validate format
            if export_format != "csv":
                return HttpResponse(
                    "Only CSV format is supported currently.",
                    status=400,
                    content_type="text/plain",
                )

            # Build queryset with filters
            queryset = self._build_queryset(filters)

            # Get audit context from request
            audit_context = get_request_audit_context(request)

            # Create CSV response
            response = self._create_csv_response(queryset)

            # Log the export operation
            log_data_export(
                user=request.user,
                export_type="persons",
                record_count=queryset.count(),
                filters=filters,
                format=export_format,
                ip_address=audit_context.get("ip_address"),
                user_agent=audit_context.get("user_agent"),
            )

            logger.info(
                f"User {request.user} exported {queryset.count()} persons "
                f"with filters: {filters}"
            )

            return response

        except Exception as e:
            logger.error(f"Error during person export: {e}", exc_info=True)
            return HttpResponse(
                "An error occurred during export. Please try again.",
                status=500,
                content_type="text/plain",
            )

    def _get_filters(self, request: HttpRequest) -> dict[str, Any]:
        """
        Extract and validate filters from request parameters.

        Args:
            request: The HTTP request

        Returns:
            Dictionary of validated filters
        """
        filters = {}

        # State filter
        state = request.GET.get("state", "").strip().upper()
        if state:
            filters["state"] = state

        # ZIP code filter
        zip_code = request.GET.get("zip_code", "").strip()
        if zip_code:
            filters["zip_code"] = zip_code

        # Age filters
        try:
            min_age = request.GET.get("min_age")
            if min_age:
                filters["min_age"] = int(min_age)
        except (ValueError, TypeError):
            pass

        try:
            max_age = request.GET.get("max_age")
            if max_age:
                filters["max_age"] = int(max_age)
        except (ValueError, TypeError):
            pass

        # Voter registration filters
        registration_status = request.GET.get("registration_status", "").strip()
        if registration_status:
            filters["registration_status"] = registration_status

        party_affiliation = request.GET.get("party_affiliation", "").strip()
        if party_affiliation:
            filters["party_affiliation"] = party_affiliation

        return filters

    def _build_queryset(self, filters: dict[str, Any]) -> QuerySet[Person]:
        """
        Build queryset with applied filters.

        Args:
            filters: Dictionary of filters to apply

        Returns:
            Filtered queryset of Person objects
        """
        queryset = Person.objects.all().select_related("voter_record")

        # Apply location filters
        if "state" in filters:
            queryset = queryset.filter(state__iexact=filters["state"])

        if "zip_code" in filters:
            queryset = queryset.filter(zip_code=filters["zip_code"])

        # Apply age filters
        if "min_age" in filters or "max_age" in filters:
            queryset = queryset.by_age_range(
                min_age=filters.get("min_age"), max_age=filters.get("max_age")
            )

        # Apply voter registration filters
        if "registration_status" in filters:
            queryset = queryset.filter(
                voter_record__registration_status=filters["registration_status"]
            )

        if "party_affiliation" in filters:
            queryset = queryset.filter(
                voter_record__party_affiliation=filters["party_affiliation"]
            )

        return queryset

    def _create_csv_response(self, queryset: QuerySet[Person]) -> HttpResponse:
        """
        Create HTTP response with CSV data.

        Args:
            queryset: QuerySet of Person objects to export

        Returns:
            HttpResponse with CSV content
        """
        # Create response with CSV content type
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"persons_export_{timestamp}.csv"

        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

        # Create CSV writer
        writer = csv.writer(response)

        # Write header row
        headers = [
            "ID",
            "First Name",
            "Middle Name",
            "Last Name",
            "Suffix",
            "Date of Birth",
            "Age",
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
            "Created At",
            "Updated At",
        ]
        writer.writerow(headers)

        # Write data rows
        for person in queryset:
            # Get voter record data if available
            voter_record = getattr(person, "voter_record", None)

            row = [
                str(person.id),
                person.first_name,
                person.middle_name,
                person.last_name,
                person.suffix,
                (
                    person.date_of_birth.strftime("%Y-%m-%d")
                    if person.date_of_birth
                    else ""
                ),
                person.age or "",
                person.get_gender_display(),
                person.email,
                person.phone_primary,
                person.phone_secondary,
                person.street_address,
                person.apartment_number,
                person.city,
                person.state,
                person.zip_code,
                person.county,
                person.occupation,
                person.employer,
                voter_record.voter_id if voter_record else "",
                voter_record.get_registration_status_display() if voter_record else "",
                voter_record.get_party_affiliation_display() if voter_record else "",
                voter_record.voter_score if voter_record else "",
                (
                    voter_record.last_voted_date.strftime("%Y-%m-%d")
                    if voter_record and voter_record.last_voted_date
                    else ""
                ),
                person.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                person.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            ]
            writer.writerow(row)

        return response
