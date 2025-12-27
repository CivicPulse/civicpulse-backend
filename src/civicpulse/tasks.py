"""Celery tasks for CivicPulse async operations."""

import csv
import logging
import os
import time
import uuid
from decimal import Decimal, InvalidOperation

from celery import shared_task
from django.contrib.gis.geos import Point
from django.db import models, transaction
from django.utils import timezone

from .models import (
    Address,
    ElectionVoter,
    GeocodingError,
    GeocodingJob,
    ImportJob,
    VoterAddress,
    VoterPhoneNumber,
    VoterRecord,
)
from .services.geocoding import get_geocoder

logger = logging.getLogger(__name__)


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
        with open(import_job.file_path, encoding="utf-8") as f:
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
                    was_created = _import_single_row(row, import_job.election, batch_id)
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


# ============================================================================
# Geocoding Tasks
# ============================================================================


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def geocode_single_address(
    self,
    model_type: str,
    model_id: str,
    address_text: str,
    job_id: str | None = None,
):
    """
    Geocode a single address and update the model's location field.

    Args:
        model_type: One of 'address', 'voter_address', 'election_voter', 'voter_record'
        model_id: UUID of the model instance
        address_text: Full address string to geocode
        job_id: Optional GeocodingJob ID for tracking
    """
    geocoder = get_geocoder()

    try:
        result = geocoder.geocode(address_text)

        if result:
            # Create Point from coordinates (lon, lat order for GIS)
            location = Point(float(result.longitude), float(result.latitude), srid=4326)

            # Update the appropriate model
            if model_type == "address":
                Address.objects.filter(pk=model_id).update(location=location)
            elif model_type == "voter_address":
                VoterAddress.objects.filter(pk=model_id).update(location=location)
            elif model_type == "election_voter":
                ElectionVoter.objects.filter(pk=model_id).update(
                    location=location,
                    latitude=result.latitude,
                    longitude=result.longitude,
                )
            elif model_type == "voter_record":
                VoterRecord.objects.filter(pk=model_id).update(
                    location=location,
                    latitude=result.latitude,
                    longitude=result.longitude,
                )

            logger.info(f"Geocoded {model_type}:{model_id} via {result.source}")

            # Update job success count if tracking
            if job_id:
                GeocodingJob.objects.filter(pk=job_id).update(
                    processed_addresses=models.F("processed_addresses") + 1,
                    success_count=models.F("success_count") + 1,
                )

            return {
                "status": "success",
                "source": result.source,
                "confidence": result.confidence,
            }
        else:
            # Geocoding failed - log error
            logger.warning(
                f"Geocoding failed for {model_type}:{model_id}: {address_text[:50]}"
            )

            if job_id:
                GeocodingJob.objects.filter(pk=job_id).update(
                    processed_addresses=models.F("processed_addresses") + 1,
                    failure_count=models.F("failure_count") + 1,
                )
                GeocodingError.objects.create(
                    job_id=job_id,
                    address_text=address_text[:500],
                    model_type=model_type,
                    model_id=model_id,
                    error_message="No geocoding result returned",
                )

            return {"status": "failed", "error": "No result"}

    except Exception as e:
        logger.error(f"Geocoding error for {model_type}:{model_id}: {e}")

        if job_id:
            GeocodingJob.objects.filter(pk=job_id).update(
                processed_addresses=models.F("processed_addresses") + 1,
                failure_count=models.F("failure_count") + 1,
            )
            GeocodingError.objects.create(
                job_id=job_id,
                address_text=address_text[:500],
                model_type=model_type,
                model_id=model_id,
                error_message=str(e)[:500],
            )

        raise  # Re-raise for retry


@shared_task(bind=True)
def geocode_batch(
    self,
    addresses: list[dict],
    job_id: str | None = None,
    rate_limit_seconds: float = 1.0,
):
    """
    Geocode a batch of addresses with rate limiting.

    Args:
        addresses: List of dicts with keys: model_type, model_id, address_text
        job_id: Optional GeocodingJob ID for tracking
        rate_limit_seconds: Delay between requests (default 1.0)
    """
    geocoder = get_geocoder()
    results = {"success": 0, "failed": 0}

    for i, addr in enumerate(addresses):
        model_type = addr["model_type"]
        model_id = addr["model_id"]
        address_text = addr["address_text"]

        try:
            result = geocoder.geocode(address_text)

            if result:
                location = Point(
                    float(result.longitude), float(result.latitude), srid=4326
                )

                # Update the model
                if model_type == "address":
                    Address.objects.filter(pk=model_id).update(location=location)
                elif model_type == "voter_address":
                    VoterAddress.objects.filter(pk=model_id).update(location=location)
                elif model_type == "election_voter":
                    ElectionVoter.objects.filter(pk=model_id).update(
                        location=location,
                        latitude=result.latitude,
                        longitude=result.longitude,
                    )
                elif model_type == "voter_record":
                    VoterRecord.objects.filter(pk=model_id).update(
                        location=location,
                        latitude=result.latitude,
                        longitude=result.longitude,
                    )

                results["success"] += 1
            else:
                results["failed"] += 1
                if job_id:
                    GeocodingError.objects.create(
                        job_id=job_id,
                        address_text=address_text[:500],
                        model_type=model_type,
                        model_id=model_id,
                        error_message="No geocoding result returned",
                    )

        except Exception as e:
            results["failed"] += 1
            logger.error(f"Batch geocoding error: {e}")
            if job_id:
                GeocodingError.objects.create(
                    job_id=job_id,
                    address_text=address_text[:500],
                    model_type=model_type,
                    model_id=model_id,
                    error_message=str(e)[:500],
                )

        # Update progress
        if job_id and (i + 1) % 10 == 0:
            GeocodingJob.objects.filter(pk=job_id).update(
                processed_addresses=i + 1,
                success_count=results["success"],
                failure_count=results["failed"],
            )

        # Rate limiting
        if i < len(addresses) - 1:
            time.sleep(rate_limit_seconds)

    # Final update
    if job_id:
        GeocodingJob.objects.filter(pk=job_id).update(
            processed_addresses=len(addresses),
            success_count=results["success"],
            failure_count=results["failed"],
        )

    return results


@shared_task(bind=True)
def geocode_election_voters(
    self,
    election_id: str,
    job_id: str | None = None,
    batch_size: int = 100,
    rate_limit_seconds: float = 1.0,
):
    """
    Geocode all ElectionVoters for an election that lack coordinates.

    Args:
        election_id: UUID of the Election
        job_id: Optional GeocodingJob ID (will create one if not provided)
        batch_size: Number of addresses to process per batch
        rate_limit_seconds: Delay between geocoding requests
    """
    from .models import Election

    election = Election.objects.get(pk=election_id)

    # Create or update job
    if job_id:
        job = GeocodingJob.objects.get(pk=job_id)
    else:
        job = GeocodingJob.objects.create(
            election=election,
            status=GeocodingJob.Status.PROCESSING,
            started_at=timezone.now(),
            task_id=self.request.id,
        )
        job_id = str(job.pk)

    # Find voters needing geocoding (have address but no coordinates)
    voters_needing_geocoding = ElectionVoter.objects.filter(
        election=election,
        location__isnull=True,
    ).prefetch_related("addresses")

    # Build address list
    addresses_to_geocode = []
    for voter in voters_needing_geocoding:
        # Try home address first
        home_addr = voter.addresses.filter(type=VoterAddress.AddressType.HOME).first()
        if home_addr:
            address_text = _build_address_string(home_addr)
            if address_text:
                addresses_to_geocode.append(
                    {
                        "model_type": "election_voter",
                        "model_id": str(voter.pk),
                        "address_text": address_text,
                    }
                )

    # Update job with total count
    job.total_addresses = len(addresses_to_geocode)
    job.status = GeocodingJob.Status.PROCESSING
    job.started_at = timezone.now()
    job.task_id = self.request.id
    job.save(update_fields=["total_addresses", "status", "started_at", "task_id"])

    if not addresses_to_geocode:
        job.status = GeocodingJob.Status.COMPLETED
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "completed_at"])
        return {"status": "completed", "message": "No addresses to geocode"}

    geocoder = get_geocoder()
    success_count = 0
    failure_count = 0

    for i, addr in enumerate(addresses_to_geocode):
        try:
            result = geocoder.geocode(addr["address_text"])

            if result:
                location = Point(
                    float(result.longitude), float(result.latitude), srid=4326
                )
                ElectionVoter.objects.filter(pk=addr["model_id"]).update(
                    location=location,
                    latitude=result.latitude,
                    longitude=result.longitude,
                )
                success_count += 1
            else:
                failure_count += 1
                GeocodingError.objects.create(
                    job=job,
                    address_text=addr["address_text"][:500],
                    model_type="election_voter",
                    model_id=addr["model_id"],
                    error_message="No geocoding result returned",
                )

        except Exception as e:
            failure_count += 1
            logger.error(f"Geocoding error: {e}")
            GeocodingError.objects.create(
                job=job,
                address_text=addr["address_text"][:500],
                model_type="election_voter",
                model_id=addr["model_id"],
                error_message=str(e)[:500],
            )

        # Update progress every 10 records
        if (i + 1) % 10 == 0:
            job.processed_addresses = i + 1
            job.success_count = success_count
            job.failure_count = failure_count
            job.save(
                update_fields=["processed_addresses", "success_count", "failure_count"]
            )

        # Rate limiting
        if i < len(addresses_to_geocode) - 1:
            time.sleep(rate_limit_seconds)

    # Final update
    job.status = GeocodingJob.Status.COMPLETED
    job.completed_at = timezone.now()
    job.processed_addresses = len(addresses_to_geocode)
    job.success_count = success_count
    job.failure_count = failure_count
    job.save()

    return {
        "status": "completed",
        "total": len(addresses_to_geocode),
        "success": success_count,
        "failed": failure_count,
    }


@shared_task(bind=True)
def geocode_import_job_voters(
    self, import_job_id: str, rate_limit_seconds: float = 1.0
):
    """
    Geocode voters from a completed import job that lack coordinates.

    Called automatically after voter import completes.

    Args:
        import_job_id: UUID of the completed ImportJob
        rate_limit_seconds: Delay between geocoding requests
    """
    import_job = ImportJob.objects.select_related("election").get(pk=import_job_id)

    if import_job.status != ImportJob.Status.COMPLETED:
        logger.warning(
            f"Import job {import_job_id} is not completed, skipping geocoding"
        )
        return {"status": "skipped", "reason": "Import not completed"}

    # Create geocoding job
    job = GeocodingJob.objects.create(
        election=import_job.election,
        status=GeocodingJob.Status.PENDING,
        task_id=self.request.id,
    )

    # Delegate to the election geocoding task
    return geocode_election_voters(
        str(import_job.election.pk),
        job_id=str(job.pk),
        rate_limit_seconds=rate_limit_seconds,
    )


def _build_address_string(addr) -> str:
    """Build a geocodable address string from an address model."""
    parts = []
    if addr.street_address:
        parts.append(addr.street_address)
    if addr.street_address_2:
        parts.append(addr.street_address_2)
    if addr.city:
        parts.append(addr.city)
    if addr.state:
        parts.append(addr.state)
    if addr.zip_code:
        parts.append(addr.zip_code)
    return ", ".join(parts) if parts else ""
