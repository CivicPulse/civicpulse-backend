#!/usr/bin/env python
"""
Migration Test Data Generator

Creates production-volume test data for migration safety validation.
This script generates realistic data volumes to test migration performance and safety.
"""

import os
import random
import sys

import django
from django.db import transaction
from django.utils import timezone
from faker import Faker

# Setup Django - dynamically detect project root
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cpback.settings.development")
django.setup()

from django.contrib.contenttypes.models import ContentType  # noqa: E402

from civicpulse.audit import AuditLog  # noqa: E402
from civicpulse.models import (  # noqa: E402
    ContactAttempt,
    PasswordHistory,
    Person,
    User,
    VoterRecord,
)

fake = Faker()


class MigrationTestDataGenerator:
    """Generates production-volume test data for migration testing."""

    def __init__(self):
        self.fake = Faker()
        self.users = []
        self.persons = []

    def create_users(self, count=100):
        """Create test users."""
        print(f"Creating {count} users...")
        users_to_create = []

        for i in range(count):
            user_data = {
                "username": f"testuser_{i:06d}",
                "email": self.fake.email(),
                "first_name": self.fake.first_name(),
                "last_name": self.fake.last_name(),
                "role": random.choice(["admin", "organizer", "volunteer", "viewer"]),
                "organization": self.fake.company(),
                "phone_number": self.fake.phone_number()[:20],
                "is_verified": random.choice([True, False]),
                "is_active": True,
            }
            users_to_create.append(User(**user_data))

        with transaction.atomic():
            User.objects.bulk_create(users_to_create, batch_size=1000)

        self.users = list(User.objects.filter(username__startswith="testuser_"))
        print(f"Created {len(self.users)} users")

    def create_persons(self, count=10000):
        """Create test persons - main entity for CRM."""
        print(f"Creating {count} persons...")
        persons_to_create = []

        for i in range(count):
            person_data = {
                "first_name": f"{self.fake.first_name()}{i}"
                if i < 100
                else self.fake.first_name(),
                "middle_name": self.fake.first_name() if random.random() > 0.7 else "",
                "last_name": f"{self.fake.last_name()}{i}"
                if i < 100
                else self.fake.last_name(),
                "suffix": random.choice(["Jr.", "Sr.", "III", ""])
                if random.random() > 0.9
                else "",
                "date_of_birth": self.fake.date_of_birth(minimum_age=18, maximum_age=90)
                if random.random() > 0.3
                else None,
                "gender": random.choice(["M", "F", "O", "U"]),
                "email": self.fake.email() if random.random() > 0.2 else "",
                "phone_primary": self.fake.phone_number()[:20]
                if random.random() > 0.1
                else "",
                "phone_secondary": self.fake.phone_number()[:20]
                if random.random() > 0.8
                else "",
                "street_address": self.fake.street_address()
                if random.random() > 0.1
                else "",
                "apartment_number": self.fake.secondary_address()
                if random.random() > 0.7
                else "",
                "city": self.fake.city() if random.random() > 0.1 else "",
                "state": self.fake.state_abbr() if random.random() > 0.1 else "",
                "zip_code": self.fake.zipcode() if random.random() > 0.1 else "",
                "county": self.fake.city() if random.random() > 0.5 else "",
                "occupation": self.fake.job() if random.random() > 0.3 else "",
                "employer": self.fake.company() if random.random() > 0.4 else "",
                "notes": self.fake.text(max_nb_chars=200)
                if random.random() > 0.6
                else "",
                "tags": [self.fake.word() for _ in range(random.randint(0, 5))],
                "created_by": random.choice(self.users) if self.users else None,
                "is_active": True,
                "deleted_at": None,
                "deleted_by": None,
            }
            persons_to_create.append(Person(**person_data))

        with transaction.atomic():
            try:
                Person.objects.bulk_create(persons_to_create, batch_size=1000)
            except Exception as e:
                print(
                    f"Warning: Some persons already exist, creating individually: {e}"
                )
                # Try creating individually to handle duplicates
                for person in persons_to_create:
                    try:
                        person.save()
                    except Exception:
                        pass  # Skip duplicates

        self.persons = list(Person.objects.all())
        print(f"Created {len(self.persons)} persons")

    def create_contact_attempts(self, count=50000):
        """Create contact attempts - high volume transactional data."""
        print(f"Creating {count} contact attempts...")
        if not self.persons or not self.users:
            print("Skipping contact attempts - need persons and users first")
            return

        contacts_to_create = []

        for _i in range(count):
            contact_data = {
                "person": random.choice(self.persons),
                "contacted_by": random.choice(self.users),
                "contact_type": random.choice(
                    [
                        "phone",
                        "text",
                        "email",
                        "door",
                        "mail",
                        "social",
                        "event",
                        "other",
                    ]
                ),
                "contact_date": timezone.make_aware(
                    self.fake.date_time_between(start_date="-2y", end_date="now")
                ),
                "result": random.choice(
                    [
                        "contacted",
                        "no_answer",
                        "left_message",
                        "wrong_number",
                        "refused",
                        "callback",
                        "not_home",
                        "moved",
                        "deceased",
                        "other",
                    ]
                ),
                "sentiment": random.choice(
                    [
                        "strong_support",
                        "support",
                        "neutral",
                        "oppose",
                        "strong_oppose",
                        "undecided",
                        "",
                    ]
                ),
                "issues_discussed": [
                    self.fake.word() for _ in range(random.randint(0, 3))
                ],
                "commitments": [self.fake.word() for _ in range(random.randint(0, 2))],
                "follow_up_required": random.choice([True, False]),
                "follow_up_date": self.fake.future_date()
                if random.random() > 0.7
                else None,
                "notes": self.fake.text(max_nb_chars=300)
                if random.random() > 0.5
                else "",
                "duration_minutes": random.randint(1, 60)
                if random.random() > 0.3
                else None,
                "campaign": f"Campaign_{random.randint(1, 10)}"
                if random.random() > 0.4
                else "",
                "event": f"Event_{random.randint(1, 20)}"
                if random.random() > 0.7
                else "",
            }
            contacts_to_create.append(ContactAttempt(**contact_data))

        with transaction.atomic():
            ContactAttempt.objects.bulk_create(contacts_to_create, batch_size=1000)

        print(f"Created {ContactAttempt.objects.count()} contact attempts")

    def create_voter_records(self, count=8000):
        """Create voter records - one-to-one with persons."""
        print(f"Creating {count} voter records...")
        if not self.persons:
            print("Skipping voter records - need persons first")
            return

        # Get persons without voter records
        persons_without_voters = self.persons[:count]
        voter_records_to_create = []

        for i, person in enumerate(persons_without_voters):
            voter_data = {
                "person": person,
                "voter_id": f"VR{1000000 + i:06d}",  # Ensure unique voter IDs
                "registration_date": self.fake.date_between(
                    start_date="-10y", end_date="now"
                )
                if random.random() > 0.1
                else None,
                "registration_status": random.choice(
                    ["active", "inactive", "pending", "cancelled", "suspended"]
                ),
                "party_affiliation": random.choice(
                    ["DEM", "REP", "IND", "GRN", "LIB", "OTH", "NON"]
                ),
                "precinct": f"P{random.randint(1, 50)}"
                if random.random() > 0.2
                else "",
                "ward": f"W{random.randint(1, 20)}" if random.random() > 0.3 else "",
                "congressional_district": f"CD{random.randint(1, 15)}"
                if random.random() > 0.1
                else "",
                "state_house_district": f"HD{random.randint(1, 100)}"
                if random.random() > 0.1
                else "",
                "state_senate_district": f"SD{random.randint(1, 50)}"
                if random.random() > 0.1
                else "",
                "polling_location": self.fake.address()
                if random.random() > 0.3
                else "",
                "voting_history": [
                    {
                        "year": y,
                        "election": f"General_{y}",
                        "voted": random.choice([True, False]),
                    }
                    for y in range(2020, 2025)
                ],
                "absentee_voter": random.choice([True, False]),
                "mail_ballot_requested": random.choice([True, False]),
                "mail_ballot_sent_date": self.fake.date_between(
                    start_date="-1y", end_date="now"
                )
                if random.random() > 0.7
                else None,
                "mail_ballot_returned_date": self.fake.date_between(
                    start_date="-1y", end_date="now"
                )
                if random.random() > 0.8
                else None,
                "last_voted_date": self.fake.date_between(
                    start_date="-4y", end_date="now"
                )
                if random.random() > 0.2
                else None,
                "voter_score": random.randint(0, 100),
                "source": random.choice(
                    ["State_Rolls", "Party_Lists", "Manual_Entry", "Import_2024"]
                ),
            }
            voter_records_to_create.append(VoterRecord(**voter_data))

        with transaction.atomic():
            try:
                VoterRecord.objects.bulk_create(
                    voter_records_to_create, batch_size=1000
                )
            except Exception as e:
                print(
                    f"Warning: Some voter records already exist, creating "
                    f"individually: {e}"
                )
                # Try creating individually to handle duplicates
                for voter_record in voter_records_to_create:
                    try:
                        voter_record.save()
                    except Exception:
                        pass  # Skip duplicates

        print(f"Created {VoterRecord.objects.count()} voter records")

    def create_password_history(self, count=500):
        """Create password history records."""
        print(f"Creating {count} password history records...")
        if not self.users:
            print("Skipping password history - need users first")
            return

        password_history_to_create = []

        for i in range(count):
            history_data = {
                "user": random.choice(self.users),
                "password_hash": f"pbkdf2_sha256$600000$test{i}$fakehash{i}",
            }
            password_history_to_create.append(PasswordHistory(**history_data))

        with transaction.atomic():
            PasswordHistory.objects.bulk_create(
                password_history_to_create, batch_size=1000
            )

        print(f"Created {PasswordHistory.objects.count()} password history records")

    def create_audit_logs(self, count=25000):
        """Create audit log records - high volume audit data."""
        print(f"Creating {count} audit log records...")
        if not self.users:
            print("Skipping audit logs - need users first")
            return

        audit_logs_to_create = []
        person_content_type = ContentType.objects.get_for_model(Person)
        user_content_type = ContentType.objects.get_for_model(User)

        for _i in range(count):
            content_type = random.choice([person_content_type, user_content_type])
            audit_data = {
                "user": random.choice(self.users) if random.random() > 0.1 else None,
                "user_repr": f"User_{random.randint(1, 100)}",
                "action": random.choice(
                    [
                        "CREATE",
                        "UPDATE",
                        "DELETE",
                        "VIEW",
                        "LOGIN",
                        "LOGOUT",
                        "EXPORT",
                        "IMPORT",
                    ]
                ),
                "category": random.choice(
                    ["VOTER_DATA", "AUTH", "SYSTEM", "CONTACT", "ADMIN", "SECURITY"]
                ),
                "severity": random.choice(["INFO", "WARNING", "ERROR", "CRITICAL"]),
                "content_type": content_type,
                "object_id": str(random.randint(1, 10000)),
                "object_repr": f"Object_{random.randint(1, 10000)}",
                "changes": {"field1": {"old": "old_value", "new": "new_value"}}
                if random.random() > 0.3
                else {},
                "old_values": {"field1": "old_value", "field2": "old_value2"}
                if random.random() > 0.5
                else {},
                "new_values": {"field1": "new_value", "field2": "new_value2"}
                if random.random() > 0.5
                else {},
                "ip_address": self.fake.ipv4() if random.random() > 0.2 else None,
                "user_agent": self.fake.user_agent() if random.random() > 0.3 else "",
                "session_key": self.fake.sha256()[:40] if random.random() > 0.4 else "",
                "message": self.fake.sentence() if random.random() > 0.3 else "",
                "metadata": {"key1": "value1", "count": random.randint(1, 100)}
                if random.random() > 0.4
                else {},
                "search_vector": self.fake.text(max_nb_chars=100)
                if random.random() > 0.5
                else "",
            }
            audit_logs_to_create.append(AuditLog(**audit_data))

        with transaction.atomic():
            AuditLog.objects.bulk_create(audit_logs_to_create, batch_size=1000)

        print(f"Created {AuditLog.objects.count()} audit log records")

    def generate_all_data(self):
        """Generate all test data in the correct order."""
        print("=== Starting Migration Test Data Generation ===")
        print("This will create production-volume test data for migration validation.")

        # Create data in dependency order - scaled down for testing
        self.create_users(50)  # 50 users
        self.create_persons(1000)  # 1k persons (main entities)
        self.create_contact_attempts(5000)  # 5k contacts (high volume)
        self.create_voter_records(800)  # 800 voter records
        self.create_password_history(100)  # 100 password history
        self.create_audit_logs(2500)  # 2.5k audit logs (high volume)

        print("\n=== Data Generation Complete ===")
        print(f"Users: {User.objects.count()}")
        print(f"Persons: {Person.objects.count()}")
        print(f"Contact Attempts: {ContactAttempt.objects.count()}")
        print(f"Voter Records: {VoterRecord.objects.count()}")
        print(f"Password History: {PasswordHistory.objects.count()}")
        print(f"Audit Logs: {AuditLog.objects.count()}")

    def cleanup_test_data(self):
        """Clean up all test data."""
        print("=== Cleaning up test data ===")
        ContactAttempt.objects.filter(
            person__created_by__username__startswith="testuser_"
        ).delete()
        VoterRecord.objects.filter(
            person__created_by__username__startswith="testuser_"
        ).delete()
        AuditLog.objects.filter(user__username__startswith="testuser_").delete()
        PasswordHistory.objects.filter(user__username__startswith="testuser_").delete()
        Person.objects.filter(created_by__username__startswith="testuser_").delete()
        User.objects.filter(username__startswith="testuser_").delete()
        print("Test data cleanup complete")


if __name__ == "__main__":
    generator = MigrationTestDataGenerator()

    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        generator.cleanup_test_data()
    else:
        generator.generate_all_data()
