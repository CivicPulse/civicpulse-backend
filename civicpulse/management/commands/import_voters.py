import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from civicpulse.models import Address, Person, PhoneNumber, VoterRecord


class Command(BaseCommand):
    help = "Import voter data from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to the CSV file to import")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse the file but don't save to database",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        dry_run = options["dry_run"]

        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_file}")
        except Exception as e:
            raise CommandError(f"Error reading file: {e}")

        total = len(rows)
        created = 0
        updated = 0
        errors = []

        self.stdout.write(f"Processing {total} rows...")

        for i, row in enumerate(rows, 1):
            try:
                if dry_run:
                    self._validate_row(row, i)
                else:
                    with transaction.atomic():
                        was_created = self._import_row(row)
                        if was_created:
                            created += 1
                        else:
                            updated += 1

                if i % 100 == 0:
                    self.stdout.write(f"Processed {i}/{total} rows...")

            except Exception as e:
                errors.append(f"Row {i}: {e}")
                if len(errors) >= 10:
                    self.stdout.write(
                        self.style.WARNING("Too many errors, stopping...")
                    )
                    break

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Dry run complete: {total} rows validated")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Import complete: {created} created, {updated} updated"
                )
            )

        if errors:
            self.stdout.write(self.style.ERROR(f"\n{len(errors)} errors:"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  {error}"))

    def _validate_row(self, row, row_num):
        """Validate a row without saving."""
        voter_id = row.get("Voter ID", "").strip()
        if not voter_id:
            raise ValueError("Missing Voter ID")

        first_name = row.get("First Name", "").strip()
        last_name = row.get("Last Name", "").strip()
        if not first_name or not last_name:
            raise ValueError("Missing first or last name")

    def _import_row(self, row):
        """Import a single row. Returns True if created, False if updated."""
        voter_id = row.get("Voter ID", "").strip()
        first_name = row.get("First Name", "").strip()
        last_name = row.get("Last Name", "").strip()

        # Get or create Person
        person, created = Person.objects.update_or_create(
            voter_id=voter_id,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        # Create or update VoterRecord
        self._update_voter_record(person, row)

        # Create or update home address
        self._update_address(person, row, address_type="home")

        # Create or update mailing address (if different from home)
        self._update_address(person, row, address_type="mailing")

        # Create or update phone number
        self._update_phone(person, row)

        return created

    def _update_voter_record(self, person, row):
        """Create or update VoterRecord for the person."""
        voter_record, _ = VoterRecord.objects.update_or_create(
            person=person,
            defaults={
                "registered_party": row.get("Registered Party", "").strip(),
                "gender": row.get("Gender", "").strip()[:1],
                "age": self._parse_int(row.get("Age", "")),
                "ethnicity": row.get("Ethnicity", "").strip(),
                "marital_status": row.get("Marital Status", "").strip(),
                "spoken_language": row.get("Spoken Language", "").strip(),
                "military_status": row.get("Military Active/Veteran", "").strip(),
                "changed_party": self._parse_bool(row.get("Voter Changed Party?", "")),
                "latitude": self._parse_decimal(row.get("Lattitude", "")),
                "longitude": self._parse_decimal(row.get("Longitude", "")),
                "apartment_type": row.get("Apartment Type", "").strip(),
                "street_number_parity": row.get("Street Number Odd/Even", "").strip(),
                "cell_phone_confidence": row.get(
                    "Cell Phone Confidence Code", ""
                ).strip(),
                "likelihood_general": row.get("Likelihood to vote", "").strip(),
                "likelihood_primary": row.get("Primary Likelihood to Vote", "").strip(),
                "likelihood_combined": row.get(
                    "Combined General and Primary Likelihood to Vote", ""
                ).strip(),
                "voted_general_2024": self._parse_bool(row.get("General_2024", "")),
                "voted_general_2022": self._parse_bool(row.get("Voted in 2022", "")),
                "voted_general_2020": self._parse_bool(row.get("Voted in 2020", "")),
                "voted_general_2018": self._parse_bool(row.get("Voted in 2018", "")),
                "voted_primary_2024": self._parse_bool(row.get("Primary_2024", "")),
                "voted_primary_2022": self._parse_bool(
                    row.get("Voted in 2022 Primary", "")
                ),
                "voted_primary_2020": self._parse_bool(
                    row.get("Voter in 2020 Primary", "")
                ),
                "voted_primary_2018": self._parse_bool(
                    row.get("Voted in 2018 Primary", "")
                ),
                "household_party": row.get("Household Party Registration", "").strip(),
                "mailing_household_size": self._parse_int(
                    row.get("Mailing Household Size", "")
                ),
                "mailing_family_id": row.get("Mailing Family ID", "").strip(),
                "mailing_household_count": self._parse_int(
                    row.get("Mailing_Families_HHCount", "")
                ),
                "mailing_household_party": row.get(
                    "Mailing Household Party Registration", ""
                ).strip(),
            },
        )

    def _update_address(self, person, row, address_type):
        """Create or update an address for the person."""
        if address_type == "home":
            street = row.get("Address", "").strip()
            street2 = row.get("Second Address Line", "").strip()
            city = row.get("City", "").strip()
            state = row.get("State", "").strip()
            zip_code = row.get("Zipcode", "").strip()
            zip4 = row.get("Zip+4", "").strip()
            addr_type = Address.AddressType.HOME
        else:
            street = row.get("Mailing Address", "").strip()
            street2 = row.get("Mailing Address Extra Line", "").strip()
            city = row.get("Mailing City", "").strip()
            state = row.get("Mailing State", "").strip()
            zip_code = row.get("Mailing Zip", "").strip()
            zip4 = row.get("Mailing Zip+4", "").strip()
            addr_type = Address.AddressType.MAILING

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

        Address.objects.update_or_create(
            person=person,
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

    def _update_phone(self, person, row):
        """Create or update phone number for the person."""
        phone = row.get("Cell Phone", "").strip()
        if not phone:
            return

        PhoneNumber.objects.update_or_create(
            person=person,
            type=PhoneNumber.PhoneType.MOBILE,
            defaults={
                "number": phone,
                "is_primary": True,
            },
        )

    def _parse_int(self, value):
        """Parse a string to integer, return None if invalid."""
        if not value or not value.strip():
            return None
        try:
            return int(value.strip())
        except ValueError:
            return None

    def _parse_decimal(self, value):
        """Parse a string to Decimal, return None if invalid."""
        if not value or not value.strip():
            return None
        try:
            return Decimal(value.strip())
        except InvalidOperation:
            return None

    def _parse_bool(self, value):
        """Parse a string to boolean, return None if empty."""
        if not value or not value.strip():
            return None
        val = value.strip().upper()
        return val in ("Y", "YES", "TRUE", "1")
