"""Celery tasks for CivicPulse async operations."""

import csv
import os
import uuid
from decimal import Decimal, InvalidOperation

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import (
    ElectionVoter,
    ImportJob,
    VoterAddress,
    VoterPhoneNumber,
)


@shared_task(bind=True)
def process_voter_import(self, import_job_id: str):
    """
    Async task to process CSV voter import.

    Creates ElectionVoter records (election-specific, completely independent).
    """
    import_job = ImportJob.objects.get(pk=import_job_id)

    try:
        # Update job status
        import_job.status = ImportJob.Status.PROCESSING
        import_job.started_at = timezone.now()
        import_job.task_id = self.request.id
        import_job.save(update_fields=["status", "started_at", "task_id"])

        # Read CSV and count rows
        with open(import_job.file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total_rows = len(rows)
        import_job.total_rows = total_rows
        import_job.save(update_fields=["total_rows"])

        batch_id = str(uuid.uuid4())
        created = 0
        updated = 0
        errors = []

        for i, row in enumerate(rows, 1):
            try:
                with transaction.atomic():
                    was_created = _import_single_row(
                        row, import_job.election, batch_id
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1
            except Exception as e:
                errors.append(f"Row {i}: {e!s}")
                if len(errors) >= 100:  # Cap error collection
                    errors.append("... additional errors truncated")
                    break

            # Update progress every 50 rows or on completion
            if i % 50 == 0 or i == total_rows:
                import_job.processed_rows = i
                import_job.created_count = created
                import_job.updated_count = updated
                import_job.error_count = len(errors)
                import_job.save(
                    update_fields=[
                        "processed_rows",
                        "created_count",
                        "updated_count",
                        "error_count",
                    ]
                )

        # Final status update
        import_job.status = ImportJob.Status.COMPLETED
        import_job.completed_at = timezone.now()
        import_job.error_messages = errors
        import_job.save()

        # Clean up temp file
        _cleanup_temp_file(import_job.file_path)

        return {
            "status": "completed",
            "created": created,
            "updated": updated,
            "errors": len(errors),
        }

    except Exception as e:
        import_job.status = ImportJob.Status.FAILED
        import_job.completed_at = timezone.now()
        import_job.error_messages = [str(e)]
        import_job.save()

        _cleanup_temp_file(import_job.file_path)
        raise


def _import_single_row(row: dict, election, batch_id: str) -> bool:
    """
    Import a single CSV row as an ElectionVoter.

    Returns True if created, False if updated.
    """
    voter_id = row.get("Voter ID", "").strip()
    if not voter_id:
        raise ValueError("Missing Voter ID")

    first_name = row.get("First Name", "").strip()
    last_name = row.get("Last Name", "").strip()
    if not first_name or not last_name:
        raise ValueError("Missing first or last name")

    # Build voting history dict from CSV fields
    voting_history = {}
    if _parse_bool(row.get("General_2024", "")):
        voting_history["general_2024"] = True
    if _parse_bool(row.get("Voted in 2022", "")):
        voting_history["general_2022"] = True
    if _parse_bool(row.get("Voted in 2020", "")):
        voting_history["general_2020"] = True
    if _parse_bool(row.get("Voted in 2018", "")):
        voting_history["general_2018"] = True
    if _parse_bool(row.get("Primary_2024", "")):
        voting_history["primary_2024"] = True
    if _parse_bool(row.get("Voted in 2022 Primary", "")):
        voting_history["primary_2022"] = True
    if _parse_bool(row.get("Voter in 2020 Primary", "")):
        voting_history["primary_2020"] = True
    if _parse_bool(row.get("Voted in 2018 Primary", "")):
        voting_history["primary_2018"] = True

    # Create or update ElectionVoter
    voter, created = ElectionVoter.objects.update_or_create(
        election=election,
        voter_id=voter_id,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "middle_name": row.get("Middle Name", "").strip(),
            "nickname": row.get("Nickname", "").strip(),
            "registered_party": row.get("Registered Party", "").strip(),
            "gender": row.get("Gender", "").strip()[:1],
            "age": _parse_int(row.get("Age", "")),
            "ethnicity": row.get("Ethnicity", "").strip(),
            "marital_status": row.get("Marital Status", "").strip(),
            "spoken_language": row.get("Spoken Language", "").strip(),
            "military_status": row.get("Military Active/Veteran", "").strip(),
            "changed_party": _parse_bool(row.get("Voter Changed Party?", "")),
            "latitude": _parse_decimal(row.get("Lattitude", "")),
            "longitude": _parse_decimal(row.get("Longitude", "")),
            "apartment_type": row.get("Apartment Type", "").strip(),
            "street_number_parity": row.get("Street Number Odd/Even", "").strip(),
            "cell_phone_confidence": row.get("Cell Phone Confidence Code", "").strip(),
            "likelihood_general": row.get("Likelihood to vote", "").strip(),
            "likelihood_primary": row.get("Primary Likelihood to Vote", "").strip(),
            "likelihood_combined": row.get(
                "Combined General and Primary Likelihood to Vote", ""
            ).strip(),
            "voting_history": voting_history,
            "household_party": row.get("Household Party Registration", "").strip(),
            "mailing_household_size": _parse_int(row.get("Mailing Household Size", "")),
            "mailing_family_id": row.get("Mailing Family ID", "").strip(),
            "mailing_household_count": _parse_int(
                row.get("Mailing_Families_HHCount", "")
            ),
            "mailing_household_party": row.get(
                "Mailing Household Party Registration", ""
            ).strip(),
            "import_batch": batch_id,
        },
    )

    # Create or update addresses
    _update_voter_address(voter, row, address_type="home")
    _update_voter_address(voter, row, address_type="mailing")

    # Create or update phone number
    _update_voter_phone(voter, row)

    return created


def _update_voter_address(voter, row, address_type):
    """Create or update an address for the election voter."""
    if address_type == "home":
        street = row.get("Address", "").strip()
        street2 = row.get("Second Address Line", "").strip()
        city = row.get("City", "").strip()
        state = row.get("State", "").strip()
        zip_code = row.get("Zipcode", "").strip()
        zip4 = row.get("Zip+4", "").strip()
        addr_type = VoterAddress.AddressType.HOME
    else:
        street = row.get("Mailing Address", "").strip()
        street2 = row.get("Mailing Address Extra Line", "").strip()
        city = row.get("Mailing City", "").strip()
        state = row.get("Mailing State", "").strip()
        zip_code = row.get("Mailing Zip", "").strip()
        zip4 = row.get("Mailing Zip+4", "").strip()
        addr_type = VoterAddress.AddressType.MAILING

    # Skip if no street address
    if not street:
        return

    # Combine zip code with zip+4 if available
    full_zip = f"{zip_code}-{zip4}" if zip4 else zip_code

    # For mailing address, check if it's different from home
    if address_type == "mailing":
        home_street = row.get("Address", "").strip()
        if street == home_street:
            # Mailing same as home, skip
            return

    VoterAddress.objects.update_or_create(
        voter=voter,
        type=addr_type,
        defaults={
            "street_address": street,
            "street_address_2": street2,
            "city": city,
            "state": state[:2] if state else "",
            "zip_code": full_zip[:10] if full_zip else "",
            "is_primary": address_type == "home",
        },
    )


def _update_voter_phone(voter, row):
    """Create or update phone number for the election voter."""
    phone = row.get("Cell Phone", "").strip()
    if not phone:
        return

    VoterPhoneNumber.objects.update_or_create(
        voter=voter,
        type=VoterPhoneNumber.PhoneType.MOBILE,
        defaults={
            "number": phone,
            "is_primary": True,
        },
    )


def _cleanup_temp_file(file_path: str):
    """Remove temporary upload file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass  # Log but don't fail


def _parse_int(value):
    """Parse a string to integer, return None if invalid."""
    if not value or not value.strip():
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _parse_decimal(value):
    """Parse a string to Decimal, return None if invalid."""
    if not value or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        return None


def _parse_bool(value):
    """Parse a string to boolean, return None if empty."""
    if not value or not value.strip():
        return None
    val = value.strip().upper()
    return val in ("Y", "YES", "TRUE", "1")
