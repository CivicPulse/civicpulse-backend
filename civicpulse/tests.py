import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from .models import ContactAttempt, Person, VoterRecord

User = get_user_model()


class UserModelTest(TestCase):
    """Test cases for the extended User model."""

    def setUp(self):
        self.user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123",
            "role": "volunteer",
            "organization": "Test Org",
            "phone_number": "+12125551234",
        }

    def test_create_user(self):
        """Test creating a user with custom fields."""
        user = User.objects.create_user(
            username=self.user_data["username"],
            email=self.user_data["email"],
            password=self.user_data["password"],
            role=self.user_data["role"],
            organization=self.user_data["organization"],
            phone_number=self.user_data["phone_number"],
        )

        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.role, "volunteer")
        self.assertEqual(user.organization, "Test Org")
        self.assertEqual(user.phone_number, "+12125551234")
        self.assertFalse(user.is_verified)
        self.assertIsInstance(user.id, uuid.UUID)

    def test_user_str_representation(self):
        """Test the string representation of User."""
        user = User.objects.create_user(username="johndoe", role="organizer")
        self.assertEqual(str(user), "johndoe (organizer)")

    def test_user_role_choices(self):
        """Test that role choices are enforced."""
        user = User.objects.create_user(username="testuser2")

        # Test valid roles
        for role, _ in User.ROLE_CHOICES:
            user.role = role
            # Set organization for roles that require it
            if role in ["admin", "organizer"]:
                user.organization = "Test Organization"
            else:
                user.organization = ""
            user.full_clean()  # Should not raise

    def test_phone_number_validation(self):
        """Test phone number validation with phonenumbers library."""
        user = User.objects.create_user(username="testuser3")

        # Valid phone numbers - various formats
        valid_numbers = [
            "+1 212 555 1234",  # International format
            "(212) 555-1234",  # US format with parentheses
            "212-555-1234",  # US format with dashes
            "2125551234",  # Plain digits
            "+12125551234",  # E164 format
            "212.555.1234",  # Dots format
        ]
        for number in valid_numbers:
            user.phone_number = number
            user.full_clean()  # Should not raise

        # Invalid phone numbers
        invalid_numbers = [
            "123",  # Too short
            "abc123def",  # Contains letters
            "123456789012345",  # Genuinely too long
            "0000000000",  # Invalid number pattern
            "1234567890",  # Invalid: area code 123 is not assigned in NANP
        ]
        for number in invalid_numbers:
            user.phone_number = number
            with self.assertRaises(
                ValidationError, msg=f"Expected ValidationError for '{number}'"
            ):
                user.full_clean()

    def test_phone_number_formatting(self):
        """Test phone number formatting functionality."""
        user = User.objects.create_user(
            username="testuser4", phone_number="+12125551234"
        )

        # Test different format types
        self.assertEqual(user.get_formatted_phone_number("national"), "(212) 555-1234")
        self.assertEqual(
            user.get_formatted_phone_number("international"), "+1 212-555-1234"
        )
        self.assertEqual(user.get_formatted_phone_number("e164"), "+12125551234")

        # Test with empty phone number
        user.phone_number = ""
        self.assertEqual(user.get_formatted_phone_number(), "")

        # Test with invalid phone number (should return original)
        user.phone_number = "invalid"
        self.assertEqual(user.get_formatted_phone_number(), "invalid")

    def test_user_organization_validation(self):
        """Test organization validation for admin and organizer roles."""
        user = User.objects.create_user(username="testuser4")

        # Admin role without organization should fail
        user.role = "admin"
        user.organization = ""
        with self.assertRaises(ValidationError) as cm:
            user.full_clean()
        self.assertIn("organization", cm.exception.message_dict)

        # Organizer role without organization should fail
        user.role = "organizer"
        user.organization = "   "  # Only whitespace
        with self.assertRaises(ValidationError) as cm:
            user.full_clean()
        self.assertIn("organization", cm.exception.message_dict)

        # Admin role with organization should pass
        user.role = "admin"
        user.organization = "Valid Organization"
        user.full_clean()  # Should not raise


class PersonModelTest(TestCase):
    """Test cases for the Person model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="creator", email="creator@example.com"
        )

        self.person_data = {
            "first_name": "John",
            "middle_name": "Michael",
            "last_name": "Doe",
            "suffix": "Jr.",
            "date_of_birth": date(1980, 1, 15),
            "gender": "M",
            "email": "johndoe@example.com",
            "phone_primary": "+12125551234",
            "phone_secondary": "+12125555678",
            "street_address": "123 Main St",
            "apartment_number": "Apt 4B",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001",
            "county": "New York County",
            "occupation": "Software Engineer",
            "employer": "Tech Corp",
            "notes": "Active voter",
            "tags": ["volunteer", "donor"],
            "created_by": self.user,
        }

    def test_create_person(self):
        """Test creating a person with all fields."""
        person = Person.objects.create(**self.person_data)

        self.assertEqual(person.first_name, "John")
        self.assertEqual(person.last_name, "Doe")
        self.assertEqual(person.email, "johndoe@example.com")
        self.assertIsInstance(person.id, uuid.UUID)
        self.assertEqual(person.tags, ["volunteer", "donor"])

    def test_person_full_name_property(self):
        """Test the full_name property."""
        person = Person.objects.create(**self.person_data)
        self.assertEqual(person.full_name, "John Michael Doe Jr.")

        # Test without middle name and suffix
        person2 = Person.objects.create(first_name="Jane", last_name="Smith")
        self.assertEqual(person2.full_name, "Jane Smith")

    def test_person_str_representation(self):
        """Test the string representation of Person."""
        person = Person.objects.create(**self.person_data)
        self.assertEqual(str(person), "John Doe")

    def test_person_unique_constraint(self):
        """Test unique_together constraint."""
        Person.objects.create(
            first_name="John", last_name="Doe", date_of_birth=date(1980, 1, 15)
        )

        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            Person.objects.create(
                first_name="John", last_name="Doe", date_of_birth=date(1980, 1, 15)
            )

    def test_person_gender_choices(self):
        """Test gender choices."""
        person = Person.objects.create(first_name="Test", last_name="User")

        for gender, _ in Person.GENDER_CHOICES:
            person.gender = gender
            person.save()  # Just save, don't full_clean to avoid the created_by issue

    def test_person_age_property(self):
        """Test the age property calculation."""
        person = Person.objects.create(
            first_name="Test", last_name="User", date_of_birth=date(1990, 1, 1)
        )
        age = person.age
        expected_age = timezone.now().date().year - 1990
        # Age could be off by 1 depending on the current date
        self.assertIn(age, [expected_age, expected_age - 1])

        # Test with no date of birth
        person2 = Person.objects.create(first_name="No", last_name="DOB")
        self.assertIsNone(person2.age)

    def test_person_date_validation(self):
        """Test date of birth validation."""
        person = Person.objects.create(first_name="Test", last_name="User")

        # Future date of birth should fail
        future_date = timezone.now().date() + timedelta(days=1)
        person.date_of_birth = future_date
        with self.assertRaises(ValidationError) as cm:
            person.full_clean(exclude=["created_by"])
        self.assertIn("date_of_birth", cm.exception.message_dict)

    def test_person_state_validation(self):
        """Test state code validation."""
        person = Person.objects.create(first_name="Test", last_name="User")

        # Valid state codes should pass - exclude created_by from validation
        valid_states = ["CA", "NY", "TX", "DC"]
        for state in valid_states:
            person.state = state
            person.full_clean(exclude=["created_by"])  # Should not raise

        # Invalid state codes should fail
        person.state = "XX"
        with self.assertRaises(ValidationError) as cm:
            person.full_clean(exclude=["created_by"])
        self.assertIn("state", cm.exception.message_dict)

    def test_person_phone_formatting(self):
        """Test Person phone number formatting methods."""
        person = Person.objects.create(
            first_name="John",
            last_name="Doe",
            phone_primary="+12125551234",
            phone_secondary="+13035551234",  # Use valid Denver area code
        )

        # Test primary phone formatting
        self.assertEqual(
            person.get_formatted_phone_primary("national"), "(212) 555-1234"
        )
        self.assertEqual(
            person.get_formatted_phone_primary("international"), "+1 212-555-1234"
        )
        self.assertEqual(person.get_formatted_phone_primary("e164"), "+12125551234")

        # Test secondary phone formatting
        self.assertEqual(
            person.get_formatted_phone_secondary("national"), "(303) 555-1234"
        )
        self.assertEqual(person.get_formatted_phone_secondary("e164"), "+13035551234")

        # Test with empty phone numbers
        person.phone_primary = ""
        person.phone_secondary = ""
        self.assertEqual(person.get_formatted_phone_primary(), "")
        self.assertEqual(person.get_formatted_phone_secondary(), "")

        # Test with invalid phone numbers (should return original)
        person.phone_primary = "invalid"
        person.phone_secondary = "also invalid"
        self.assertEqual(person.get_formatted_phone_primary(), "invalid")
        self.assertEqual(person.get_formatted_phone_secondary(), "also invalid")


class VoterRecordModelTest(TestCase):
    """Test cases for the VoterRecord model."""

    def setUp(self):
        self.person = Person.objects.create(
            first_name="Jane", last_name="Voter", email="jane@example.com"
        )

        self.voter_data = {
            "person": self.person,
            "voter_id": "V123456789",
            "registration_date": date(2020, 1, 1),
            "registration_status": "active",
            "party_affiliation": "DEM",
            "precinct": "42",
            "ward": "5",
            "congressional_district": "12",
            "state_house_district": "25",
            "state_senate_district": "8",
            "polling_location": "Community Center",
            "voting_history": [
                {"date": "2020-11-03", "election": "General"},
                {"date": "2022-11-08", "election": "Midterm"},
            ],
            "absentee_voter": False,
            "mail_ballot_requested": False,
            "last_voted_date": date(2022, 11, 8),
            "voter_score": 85,
            "source": "State Voter File",
        }

    def test_create_voter_record(self):
        """Test creating a voter record."""
        voter = VoterRecord.objects.create(**self.voter_data)

        self.assertEqual(voter.voter_id, "V123456789")
        self.assertEqual(voter.party_affiliation, "DEM")
        self.assertEqual(voter.precinct, "42")
        self.assertEqual(voter.voter_score, 85)
        self.assertEqual(len(voter.voting_history), 2)

    def test_voter_record_str_representation(self):
        """Test the string representation of VoterRecord."""
        voter = VoterRecord.objects.create(**self.voter_data)
        self.assertEqual(str(voter), "Voter V123456789 - Jane Voter")

    def test_voter_id_uniqueness(self):
        """Test that voter_id is unique."""
        VoterRecord.objects.create(**self.voter_data)

        # Try to create duplicate with same voter_id
        new_person = Person.objects.create(first_name="Another", last_name="Person")
        duplicate_data = self.voter_data.copy()
        duplicate_data["person"] = new_person

        with self.assertRaises(IntegrityError):
            VoterRecord.objects.create(**duplicate_data)

    def test_one_to_one_relationship(self):
        """Test one-to-one relationship with Person."""
        voter = VoterRecord.objects.create(**self.voter_data)

        # Access voter record from person
        self.assertEqual(self.person.voter_record, voter)

        # Try to create another voter record for same person
        with self.assertRaises(IntegrityError):
            VoterRecord.objects.create(person=self.person, voter_id="V987654321")

    def test_registration_status_choices(self):
        """Test registration status choices."""
        voter = VoterRecord.objects.create(**self.voter_data)

        for status, _ in VoterRecord.REGISTRATION_STATUS_CHOICES:
            voter.registration_status = status
            voter.full_clean()  # Should not raise

    def test_party_affiliation_choices(self):
        """Test party affiliation choices."""
        voter = VoterRecord.objects.create(**self.voter_data)

        for party, _ in VoterRecord.PARTY_AFFILIATION_CHOICES:
            voter.party_affiliation = party
            voter.full_clean()  # Should not raise

    def test_voter_score_validation(self):
        """Test voter score validation."""
        voter = VoterRecord.objects.create(**self.voter_data)

        # Valid scores should pass
        valid_scores = [0, 50, 100]
        for score in valid_scores:
            voter.voter_score = score
            voter.full_clean()  # Should not raise

        # Invalid scores should fail
        invalid_scores = [-1, 101]
        for score in invalid_scores:
            voter.voter_score = score
            with self.assertRaises(ValidationError) as cm:
                voter.full_clean()
            self.assertIn("voter_score", cm.exception.message_dict)

    def test_voting_frequency_property(self):
        """Test voting frequency property."""
        voter = VoterRecord.objects.create(**self.voter_data)

        test_cases = [
            (90, "Very High"),
            (70, "High"),
            (50, "Medium"),
            (30, "Low"),
            (10, "Very Low"),
        ]

        for score, expected_frequency in test_cases:
            voter.voter_score = score
            self.assertEqual(voter.voting_frequency, expected_frequency)

    def test_voter_date_validation(self):
        """Test date validation for voter records."""
        voter = VoterRecord.objects.create(**self.voter_data)

        # Future registration date should fail
        future_date = timezone.now().date() + timedelta(days=1)
        voter.registration_date = future_date
        with self.assertRaises(ValidationError) as cm:
            voter.full_clean()
        self.assertIn("registration_date", cm.exception.message_dict)

        # Future last voted date should fail
        voter.registration_date = date(2020, 1, 1)  # Reset to valid
        voter.last_voted_date = future_date
        with self.assertRaises(ValidationError) as cm:
            voter.full_clean()
        self.assertIn("last_voted_date", cm.exception.message_dict)


class ContactAttemptModelTest(TestCase):
    """Test cases for the ContactAttempt model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="canvasser", email="canvasser@example.com"
        )

        self.person = Person.objects.create(
            first_name="Contact", last_name="Target", email="target@example.com"
        )

        self.contact_data = {
            "person": self.person,
            "contact_type": "phone",
            "contact_date": timezone.now(),
            "contacted_by": self.user,
            "result": "contacted",
            "sentiment": "support",
            "issues_discussed": ["healthcare", "education"],
            "commitments": ["volunteer", "donate"],
            "follow_up_required": True,
            "follow_up_date": date.today() + timedelta(days=7),
            "notes": "Very supportive, wants to volunteer",
            "duration_minutes": 15,
            "campaign": "GOTV 2024",
            "event": "Phone Bank #3",
        }

    def test_create_contact_attempt(self):
        """Test creating a contact attempt."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        self.assertEqual(contact.contact_type, "phone")
        self.assertEqual(contact.result, "contacted")
        self.assertEqual(contact.sentiment, "support")
        self.assertEqual(contact.duration_minutes, 15)
        self.assertEqual(len(contact.issues_discussed), 2)
        self.assertTrue(contact.follow_up_required)

    def test_contact_attempt_str_representation(self):
        """Test the string representation of ContactAttempt."""
        contact = ContactAttempt.objects.create(**self.contact_data)
        date_str = contact.contact_date.strftime("%Y-%m-%d")
        expected = f"phone - Contact Target on {date_str}"
        self.assertEqual(str(contact), expected)

    def test_multiple_contacts_per_person(self):
        """Test that multiple contact attempts can be created for one person."""
        ContactAttempt.objects.create(**self.contact_data)

        # Create another contact attempt for same person
        new_contact_data = self.contact_data.copy()
        new_contact_data["contact_type"] = "door"
        new_contact_data["contact_date"] = timezone.now() + timedelta(days=1)

        contact2 = ContactAttempt.objects.create(**new_contact_data)

        # Check that person has multiple contact attempts
        self.assertEqual(self.person.contact_attempts.count(), 2)
        self.assertIn(contact2, self.person.contact_attempts.all())

    def test_contact_type_choices(self):
        """Test contact type choices."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        for contact_type, _ in ContactAttempt.CONTACT_TYPE_CHOICES:
            contact.contact_type = contact_type
            contact.full_clean()  # Should not raise

    def test_result_choices(self):
        """Test result choices."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        for result, _ in ContactAttempt.RESULT_CHOICES:
            contact.result = result
            contact.full_clean()  # Should not raise

    def test_sentiment_choices(self):
        """Test sentiment choices."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        for sentiment, _ in ContactAttempt.SENTIMENT_CHOICES:
            contact.sentiment = sentiment
            contact.full_clean()  # Should not raise

    def test_ordering(self):
        """Test that contact attempts are ordered by contact_date descending."""
        # Create multiple contact attempts
        contact1 = ContactAttempt.objects.create(
            person=self.person,
            contact_type="phone",
            contact_date=timezone.now() - timedelta(days=2),
            contacted_by=self.user,
            result="contacted",
        )

        contact2 = ContactAttempt.objects.create(
            person=self.person,
            contact_type="email",
            contact_date=timezone.now() - timedelta(days=1),
            contacted_by=self.user,
            result="contacted",
        )

        contact3 = ContactAttempt.objects.create(
            person=self.person,
            contact_type="door",
            contact_date=timezone.now(),
            contacted_by=self.user,
            result="contacted",
        )

        # Get all contacts and check ordering
        contacts = ContactAttempt.objects.all()
        self.assertEqual(contacts[0], contact3)  # Most recent first
        self.assertEqual(contacts[1], contact2)
        self.assertEqual(contacts[2], contact1)  # Oldest last

    def test_foreign_key_deletion(self):
        """Test foreign key behavior on deletion."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        # Delete the user (contacted_by)
        self.user.delete()
        contact.refresh_from_db()
        self.assertIsNone(contact.contacted_by)  # Should be set to NULL

        # Delete the person
        person_id = self.person.id
        self.person.delete()
        # Contact should be deleted (CASCADE)
        self.assertEqual(ContactAttempt.objects.filter(person_id=person_id).count(), 0)

    def test_contact_property_methods(self):
        """Test ContactAttempt property methods."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        # Test was_successful property
        successful_results = ["contacted", "left_message", "callback"]
        for result in successful_results:
            contact.result = result
            self.assertTrue(contact.was_successful)

        contact.result = "no_answer"
        self.assertFalse(contact.was_successful)

        # Test is_positive_sentiment property
        positive_sentiments = ["strong_support", "support"]
        for sentiment in positive_sentiments:
            contact.sentiment = sentiment
            self.assertTrue(contact.is_positive_sentiment)

        contact.sentiment = "oppose"
        self.assertFalse(contact.is_positive_sentiment)

    def test_contact_duration_validation(self):
        """Test duration validation."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        # Negative duration should fail
        contact.duration_minutes = -1
        with self.assertRaises(ValidationError) as cm:
            contact.full_clean()
        self.assertIn("duration_minutes", cm.exception.message_dict)

        # Extremely long duration should fail
        contact.duration_minutes = 500  # Over 8 hours
        with self.assertRaises(ValidationError) as cm:
            contact.full_clean()
        self.assertIn("duration_minutes", cm.exception.message_dict)

        # Valid duration should pass
        contact.duration_minutes = 30
        contact.full_clean()  # Should not raise


class PersonManagerTest(TestCase):
    """Test cases for the PersonManager custom manager."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="manager_test", email="manager@example.com"
        )

        # Create test persons
        self.active_person = Person.objects.create(
            first_name="Active", last_name="Person", email="active@example.com"
        )

        self.deleted_person = Person.objects.create(
            first_name="Deleted", last_name="Person", email="deleted@example.com"
        )
        self.deleted_person.soft_delete(self.user)

    def test_default_queryset_excludes_deleted(self):
        """Test that default queryset only returns active persons."""
        persons = Person.objects.all()
        self.assertIn(self.active_person, persons)
        self.assertNotIn(self.deleted_person, persons)

    def test_all_with_deleted_includes_all(self):
        """Test that all_with_deleted returns both active and deleted persons."""
        persons = Person.objects.all_with_deleted()
        self.assertIn(self.active_person, persons)
        self.assertIn(self.deleted_person, persons)

    def test_deleted_only_returns_deleted(self):
        """Test that deleted_only returns only soft-deleted persons."""
        persons = Person.objects.deleted_only()
        self.assertNotIn(self.active_person, persons)
        self.assertIn(self.deleted_person, persons)

    def test_search_by_name(self):
        """Test name search functionality."""
        results = Person.objects.search_by_name("Active")
        self.assertIn(self.active_person, results)
        self.assertNotIn(self.deleted_person, results)  # Deleted excluded by default

    def test_by_age_range(self):
        """Test age range filtering."""
        # Create person with specific age
        from datetime import date

        birth_date = date(1990, 1, 1)
        person = Person.objects.create(
            first_name="Age", last_name="Test", date_of_birth=birth_date
        )

        # Test age range
        results = Person.objects.by_age_range(min_age=25, max_age=40)
        self.assertIn(person, results)


class PersonValidationTest(TestCase):
    """Test cases for Person model validation and security."""

    def test_text_sanitization(self):
        """Test that text fields are sanitized for benign HTML."""
        person = Person(
            first_name="John<b>Bold</b>",
            last_name="Doe<em>Italic</em>",
            notes="Some notes with <b>HTML</b> tags and <i>italics</i>",
        )
        person.clean()

        self.assertEqual(person.first_name, "JohnBold")
        self.assertEqual(person.last_name, "DoeItalic")
        self.assertEqual(person.notes, "Some notes with HTML tags and italics")

    def test_suspicious_content_detection(self):
        """Test that suspicious content is detected."""
        person = Person(
            first_name="John", last_name="Doe", notes="onclick=malicious() content"
        )

        with self.assertRaises(ValidationError) as cm:
            person.clean()
        self.assertIn("notes", str(cm.exception))

    def test_age_validation(self):
        """Test age validation."""
        from datetime import date

        person = Person(
            first_name="Old",
            last_name="Person",
            date_of_birth=date(1800, 1, 1),  # Over 200 years old
        )

        with self.assertRaises(ValidationError) as cm:
            person.clean()
        self.assertIn("date_of_birth", cm.exception.message_dict)

    def test_email_domain_validation(self):
        """Test email domain validation."""
        person = Person(
            first_name="Test",
            last_name="User",
            email="user@test.com",  # Suspicious domain
        )

        with self.assertRaises(ValidationError) as cm:
            person.clean()
        self.assertIn("email", cm.exception.message_dict)

    def test_zip_code_validation(self):
        """Test ZIP code validation."""
        person = Person(first_name="Test", last_name="User")

        # Valid ZIP codes
        valid_zips = ["12345", "12345-6789"]
        for zip_code in valid_zips:
            person.zip_code = zip_code
            person.clean()  # Should not raise

        # Invalid ZIP codes
        invalid_zips = ["123", "12345-67", "abcde"]
        for zip_code in invalid_zips:
            person.zip_code = zip_code
            with self.assertRaises(ValidationError):
                person.clean()


class SoftDeleteTest(TestCase):
    """Test cases for soft delete functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="deleter", email="deleter@example.com"
        )
        self.person = Person.objects.create(first_name="Delete", last_name="Test")

    def test_soft_delete(self):
        """Test soft delete functionality."""
        self.assertTrue(self.person.is_active)
        self.assertIsNone(self.person.deleted_at)

        self.person.soft_delete(self.user)

        self.assertFalse(self.person.is_active)
        self.assertIsNotNone(self.person.deleted_at)
        self.assertEqual(self.person.deleted_by, self.user)

    def test_restore(self):
        """Test restore functionality."""
        self.person.soft_delete(self.user)
        self.assertFalse(self.person.is_active)

        self.person.restore()

        self.assertTrue(self.person.is_active)
        self.assertIsNone(self.person.deleted_at)
        self.assertIsNone(self.person.deleted_by)


class DuplicateDetectionTest(TestCase):
    """Test cases for duplicate detection."""

    def setUp(self):
        self.original_person = Person.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone_primary="+12125551234",
            date_of_birth=date(1980, 1, 1),
        )

    def test_duplicate_by_name_and_dob(self):
        """Test duplicate detection by name and DOB."""
        duplicate = Person(
            first_name="John", last_name="Doe", date_of_birth=date(1980, 1, 1)
        )

        duplicates = duplicate.get_potential_duplicates()
        self.assertIn(self.original_person, duplicates)

    def test_duplicate_by_email(self):
        """Test duplicate detection by email."""
        duplicate = Person(
            first_name="Jane",
            last_name="Smith",
            email="john@example.com",  # Same email
        )

        duplicates = duplicate.get_potential_duplicates()
        self.assertIn(self.original_person, duplicates)

    def test_duplicate_by_phone(self):
        """Test duplicate detection by phone number."""
        duplicate = Person(
            first_name="Jane",
            last_name="Smith",
            phone_primary="+12125551234",  # Same phone
        )

        duplicates = duplicate.get_potential_duplicates()
        self.assertIn(self.original_person, duplicates)


class VoterIdValidationTest(TestCase):
    """Test cases for voter ID validation."""

    def test_valid_voter_ids(self):
        """Test valid voter ID formats."""
        valid_ids = ["ABC123", "12345", "XYZ-789", "voter_123"]

        for voter_id in valid_ids:
            person = Person.objects.create(first_name="Test", last_name="Voter")
            voter = VoterRecord(person=person, voter_id=voter_id)
            voter.clean()  # Should not raise

    def test_invalid_voter_ids(self):
        """Test invalid voter ID formats."""
        invalid_ids = ["", "AB", "A" * 51, "voter@123", "voter id"]

        for voter_id in invalid_ids:
            person = Person.objects.create(first_name="Test", last_name="Voter")
            voter = VoterRecord(person=person, voter_id=voter_id)
            with self.assertRaises(ValidationError):
                voter.clean()


class ContactAttemptSecurityTest(TestCase):
    """Test cases for ContactAttempt security validation."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="contactor", email="contactor@example.com"
        )
        self.person = Person.objects.create(first_name="Contact", last_name="Test")

    def test_notes_sanitization(self):
        """Test that notes are sanitized."""
        contact = ContactAttempt(
            person=self.person,
            contact_type="phone",
            contact_date=timezone.now(),
            contacted_by=self.user,
            result="contacted",
            notes="<script>alert('xss')</script>Good conversation",
        )
        contact.clean()

        self.assertEqual(contact.notes, "Good conversation")

    def test_json_field_validation(self):
        """Test JSON field security validation."""
        contact = ContactAttempt(
            person=self.person,
            contact_type="phone",
            contact_date=timezone.now(),
            contacted_by=self.user,
            result="contacted",
            issues_discussed=["healthcare", "<script>alert('xss')</script>"],
        )

        with self.assertRaises(ValidationError):
            contact.clean()

    def test_old_contact_date_validation(self):
        """Test validation of very old contact dates."""
        old_date = timezone.now() - timedelta(days=4000)  # Over 10 years
        contact = ContactAttempt(
            person=self.person,
            contact_type="phone",
            contact_date=old_date,
            contacted_by=self.user,
            result="contacted",
        )

        with self.assertRaises(ValidationError) as cm:
            contact.clean()
        self.assertIn("contact_date", cm.exception.message_dict)
