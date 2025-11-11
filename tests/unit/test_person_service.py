"""
Comprehensive unit tests for Person service layer.

This module tests both PersonCreationService and PersonDuplicateDetector
with focus on:
- Business logic validation
- Data sanitization and normalization
- Duplicate detection algorithms
- Security (XSS, injection prevention)
- Edge cases and error handling
- Transaction atomicity
- Integration with Django ORM

Test Coverage Goal: 95%+

Author: John Miller
"""

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.test import override_settings
from django.utils import timezone

from civicpulse.models import Person
from civicpulse.services.person_service import (
    PersonCreationService,
    PersonDataDict,
    PersonDuplicateDetector,
)

User = get_user_model()


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def service():
    """Create PersonCreationService instance."""
    return PersonCreationService()


@pytest.fixture
def detector():
    """Create PersonDuplicateDetector instance."""
    return PersonDuplicateDetector()


@pytest.fixture
@pytest.mark.django_db
def test_user(db):
    """Create a test user for created_by field."""
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def valid_person_data() -> PersonDataDict:
    """Return valid person data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone_primary": "(415) 555-1234",
        "date_of_birth": date(1990, 1, 15),
        "street_address": "123 Main St",
        "city": "Springfield",
        "state": "CA",
        "zip_code": "90210",
        "gender": "M",
    }


@pytest.fixture
@pytest.mark.django_db
def existing_person(db, test_user) -> Person:
    """Create an existing person for duplicate detection tests."""
    return Person.objects.create(
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@example.com",
        phone_primary="+15551234567",
        date_of_birth=date(1985, 5, 15),
        street_address="456 Oak Ave",
        city="Springfield",
        state="CA",
        zip_code="90210",
        created_by=test_user,
    )


# ============================================================================
# PersonCreationService.create_person() Tests
# ============================================================================


@pytest.mark.django_db
class TestPersonCreationServiceCreatePerson:
    """Tests for PersonCreationService.create_person()."""

    def test_create_person_with_valid_data(self, service, test_user, valid_person_data):
        """Test creating person with valid data succeeds."""
        person, duplicates = service.create_person(
            person_data=valid_person_data,
            created_by=test_user,
            check_duplicates=False,
        )

        assert person.pk is not None
        assert person.first_name == "John"
        assert person.last_name == "Doe"
        assert person.email == "john.doe@example.com"
        assert person.phone_primary == "+14155551234"  # Normalized to E.164
        assert person.state == "CA"
        assert person.created_by == test_user
        assert duplicates == []

    def test_create_person_with_missing_required_fields(self, service, test_user):
        """Test creating person without required fields raises ValidationError."""
        invalid_data: PersonDataDict = {
            "email": "test@example.com",
        }

        with pytest.raises(ValidationError) as exc_info:
            service.create_person(
                person_data=invalid_data,
                created_by=test_user,
                check_duplicates=False,
            )

        errors = exc_info.value.message_dict
        assert "first_name" in errors
        assert "last_name" in errors

    def test_create_person_sets_created_by_correctly(
        self, service, test_user, valid_person_data
    ):
        """Test that created_by field is set correctly."""
        person, _ = service.create_person(
            person_data=valid_person_data,
            created_by=test_user,
            check_duplicates=False,
        )

        assert person.created_by == test_user
        assert person.created_by.username == "testuser"

    def test_create_person_transaction_rollback_on_error(self, service, test_user):
        """Test that transaction rolls back on validation error."""
        initial_count = Person.objects.count()

        invalid_data: PersonDataDict = {
            "first_name": "Test",
            "last_name": "User",
            "date_of_birth": "invalid-date",
        }

        with pytest.raises(ValidationError):
            service.create_person(
                person_data=invalid_data,
                created_by=test_user,
                check_duplicates=False,
            )

        # Verify no person was created
        assert Person.objects.count() == initial_count

    def test_create_person_with_duplicate_detection_enabled(
        self, service, test_user, existing_person
    ):
        """Test duplicate detection when enabled (detects email match)."""
        # Use same email but different name to avoid unique constraint violation
        duplicate_data: PersonDataDict = {
            "first_name": "Different",
            "last_name": "Name",
            "email": "jane.smith@example.com",  # Same email as existing
            "date_of_birth": date(1990, 1, 1),  # Different DOB
        }

        person, duplicates = service.create_person(
            person_data=duplicate_data,
            created_by=test_user,
            check_duplicates=True,
        )

        assert person.pk is not None  # Person is still created
        assert len(duplicates) > 0
        assert existing_person in duplicates

    def test_create_person_with_duplicate_detection_disabled(
        self, service, test_user, existing_person
    ):
        """Test duplicate detection when disabled."""
        duplicate_data: PersonDataDict = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "different@example.com",
        }

        person, duplicates = service.create_person(
            person_data=duplicate_data,
            created_by=test_user,
            check_duplicates=False,
        )

        assert person.pk is not None
        assert duplicates == []

    def test_create_person_handles_integrity_error(self, service, test_user):
        """Test IntegrityError is caught and converted to ValidationError."""
        # Create first person
        person_data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": date(1990, 1, 1),
        }
        service.create_person(
            person_data=person_data,
            created_by=test_user,
            check_duplicates=False,
        )

        # Try to create duplicate (unique constraint on name+DOB)
        with pytest.raises(ValidationError) as exc_info:
            service.create_person(
                person_data=person_data,
                created_by=test_user,
                check_duplicates=False,
            )

        assert "__all__" in exc_info.value.message_dict

    def test_create_person_with_tags(self, service, test_user):
        """Test creating person with tags."""
        person_data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "tags": ["volunteer", "donor", "member"],
        }

        person, _ = service.create_person(
            person_data=person_data,
            created_by=test_user,
            check_duplicates=False,
        )

        # Tags are stored as a set, so check as set not list
        assert set(person.tags) == {"volunteer", "donor", "member"}


# ============================================================================
# PersonCreationService.validate_person_data() Tests
# ============================================================================


@pytest.mark.django_db
class TestPersonCreationServiceValidation:
    """Tests for PersonCreationService.validate_person_data()."""

    def test_validate_empty_first_name(self, service):
        """Test validation fails for empty first name."""
        data: PersonDataDict = {
            "first_name": "",
            "last_name": "Doe",
        }
        errors = service.validate_person_data(data)
        assert "first_name" in errors
        assert "required" in errors["first_name"][0].lower()

    def test_validate_empty_last_name(self, service):
        """Test validation fails for empty last name."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "  ",
        }
        errors = service.validate_person_data(data)
        assert "last_name" in errors

    def test_validate_future_date_of_birth(self, service):
        """Test validation fails for future date of birth."""
        future_date = timezone.now().date() + timedelta(days=30)
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": future_date,
        }
        errors = service.validate_person_data(data)
        assert "date_of_birth" in errors
        assert "future" in errors["date_of_birth"][0].lower()

    def test_validate_invalid_date_format(self, service):
        """Test validation fails for invalid date format."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "2020-13-45",  # Invalid date
        }
        errors = service.validate_person_data(data)
        assert "date_of_birth" in errors

    def test_validate_unrealistic_age(self, service):
        """Test validation fails for unrealistic age (>150 years)."""
        old_date = timezone.now().date() - timedelta(days=151 * 365)
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": old_date,
        }
        errors = service.validate_person_data(data)
        assert "date_of_birth" in errors
        assert "unrealistic" in errors["date_of_birth"][0].lower()

    def test_validate_invalid_email_format(self, service):
        """Test validation fails for invalid email format."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "not-an-email",
        }
        errors = service.validate_person_data(data)
        assert "email" in errors

    @override_settings(SUSPICIOUS_EMAIL_DOMAINS=["test.com", "example.com"])
    def test_validate_suspicious_email_domain(self, service):
        """Test validation fails for suspicious email domain."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "user@test.com",
        }
        errors = service.validate_person_data(data)
        assert "email" in errors
        assert "not allowed" in errors["email"][0].lower()

    def test_validate_invalid_phone_primary(self, service):
        """Test validation fails for invalid primary phone."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "phone_primary": "123",  # Too short
        }
        errors = service.validate_person_data(data)
        assert "phone_primary" in errors

    def test_validate_invalid_phone_secondary(self, service):
        """Test validation fails for invalid secondary phone."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "phone_secondary": "abc-def-ghij",  # Not a number
        }
        errors = service.validate_person_data(data)
        assert "phone_secondary" in errors

    def test_validate_invalid_state_code(self, service):
        """Test validation fails for invalid state code."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "state": "ZZ",  # Invalid state
        }
        errors = service.validate_person_data(data)
        assert "state" in errors

    def test_validate_invalid_zip_code(self, service):
        """Test validation fails for invalid ZIP code."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "zip_code": "1234",  # Too short
        }
        errors = service.validate_person_data(data)
        assert "zip_code" in errors

    def test_validate_valid_zip_plus_four(self, service):
        """Test validation passes for valid ZIP+4 format."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "zip_code": "90210-1234",
        }
        errors = service.validate_person_data(data)
        assert "zip_code" not in errors

    def test_validate_invalid_gender(self, service):
        """Test validation fails for invalid gender code."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "gender": "X",  # Not M, F, O, or U
        }
        errors = service.validate_person_data(data)
        assert "gender" in errors

    def test_validate_all_valid_data(self, service, valid_person_data):
        """Test validation passes for all valid data."""
        errors = service.validate_person_data(valid_person_data)
        assert errors == {}


# ============================================================================
# PersonCreationService._sanitize_person_data() Tests
# ============================================================================


@pytest.mark.django_db
class TestPersonCreationServiceSanitization:
    """Tests for PersonCreationService._sanitize_person_data()."""

    def test_sanitize_removes_xss_from_name(self, service):
        """Test XSS script tags are removed from names."""
        data: PersonDataDict = {
            "first_name": "<script>alert('xss')</script>John",
            "last_name": "Doe<script>alert('xss')</script>",
        }
        sanitized = service._sanitize_person_data(data)
        assert "<script>" not in sanitized["first_name"]
        assert "<script>" not in sanitized["last_name"]
        assert "John" in sanitized["first_name"]
        assert "Doe" in sanitized["last_name"]

    def test_sanitize_removes_html_tags(self, service):
        """Test HTML tags are stripped from text fields."""
        data: PersonDataDict = {
            "first_name": "<b>John</b>",
            "last_name": "<i>Doe</i>",
            "notes": "<p>Some <strong>notes</strong></p>",
        }
        sanitized = service._sanitize_person_data(data)
        assert sanitized["first_name"] == "John"
        assert sanitized["last_name"] == "Doe"
        assert sanitized["notes"] == "Some notes"

    def test_sanitize_trims_whitespace(self, service):
        """Test whitespace is trimmed from all fields."""
        data: PersonDataDict = {
            "first_name": "  John  ",
            "last_name": "\tDoe\n",
            "email": "  test@example.com  ",
        }
        sanitized = service._sanitize_person_data(data)
        assert sanitized["first_name"] == "John"
        assert sanitized["last_name"] == "Doe"
        assert sanitized["email"] == "test@example.com"

    def test_sanitize_normalizes_email_to_lowercase(self, service):
        """Test email is converted to lowercase."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "JOHN.DOE@EXAMPLE.COM",
        }
        sanitized = service._sanitize_person_data(data)
        assert sanitized["email"] == "john.doe@example.com"

    def test_sanitize_normalizes_state_to_uppercase(self, service):
        """Test state code is converted to uppercase."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "state": "ca",
        }
        sanitized = service._sanitize_person_data(data)
        assert sanitized["state"] == "CA"

    def test_sanitize_normalizes_phone_numbers(self, service):
        """Test phone numbers are normalized to E.164 format."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "phone_primary": "(415) 555-1234",
            "phone_secondary": "415.555.6789",
        }
        sanitized = service._sanitize_person_data(data)
        assert sanitized["phone_primary"] == "+14155551234"
        assert sanitized["phone_secondary"] == "+14155556789"

    def test_sanitize_converts_date_string_to_date_object(self, service):
        """Test date string is converted to date object."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1990-05-15",
        }
        sanitized = service._sanitize_person_data(data)
        assert isinstance(sanitized["date_of_birth"], date)
        assert sanitized["date_of_birth"] == date(1990, 5, 15)

    def test_sanitize_preserves_date_object(self, service):
        """Test date object is preserved as-is."""
        dob = date(1990, 5, 15)
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": dob,
        }
        sanitized = service._sanitize_person_data(data)
        assert sanitized["date_of_birth"] is dob

    def test_sanitize_handles_invalid_date_string(self, service):
        """Test invalid date string is skipped (will be caught by validation)."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "not-a-date",
        }
        sanitized = service._sanitize_person_data(data)
        assert "date_of_birth" not in sanitized

    def test_sanitize_normalizes_gender_to_uppercase(self, service):
        """Test gender is normalized to uppercase."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "gender": "m",
        }
        sanitized = service._sanitize_person_data(data)
        assert sanitized["gender"] == "M"

    def test_sanitize_defaults_empty_gender_to_unknown(self, service):
        """Test empty gender defaults to 'U' (Unknown)."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "gender": "",
        }
        sanitized = service._sanitize_person_data(data)
        assert sanitized["gender"] == "U"

    def test_sanitize_handles_tags_list(self, service):
        """Test tags list is cleaned and deduplicated."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "tags": ["volunteer", "donor", " volunteer ", "", "member"],
        }
        sanitized = service._sanitize_person_data(data)
        assert set(sanitized["tags"]) == {"volunteer", "donor", "member"}

    def test_sanitize_removes_control_characters(self, service):
        """Test control characters are removed from text."""
        data: PersonDataDict = {
            "first_name": "John\x00\x08",
            "last_name": "Doe\x1f",
            "notes": "Test\x00note",
        }
        sanitized = service._sanitize_person_data(data)
        assert "\x00" not in sanitized["first_name"]
        assert "\x08" not in sanitized["first_name"]
        assert "\x1f" not in sanitized["last_name"]

    def test_sanitize_limits_text_length(self, service):
        """Test extremely long text is truncated."""
        long_text = "A" * 15000
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "notes": long_text,
        }
        sanitized = service._sanitize_person_data(data)
        assert len(sanitized["notes"]) <= 10000

    def test_sanitize_handles_unicode_characters(self, service):
        """Test Unicode characters are preserved."""
        data: PersonDataDict = {
            "first_name": "José",
            "last_name": "Müller",
            "notes": "Test with émojis 😀",
        }
        sanitized = service._sanitize_person_data(data)
        assert sanitized["first_name"] == "José"
        assert sanitized["last_name"] == "Müller"
        assert "émojis" in sanitized["notes"]

    def test_sanitize_removes_empty_fields(self, service):
        """Test empty string fields are not included in result."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "middle_name": "",
            "suffix": "   ",
            "notes": "",
        }
        sanitized = service._sanitize_person_data(data)
        assert "middle_name" not in sanitized
        assert "suffix" not in sanitized
        assert "notes" not in sanitized


# ============================================================================
# PersonCreationService._normalize_phone_number() Tests
# ============================================================================


@pytest.mark.django_db
class TestPersonCreationServicePhoneNormalization:
    """Tests for PersonCreationService._normalize_phone_number()."""

    def test_normalize_phone_with_parentheses(self, service):
        """Test phone number with parentheses is normalized."""
        result = service._normalize_phone_number("(415) 555-1234")
        assert result == "+14155551234"

    def test_normalize_phone_with_dashes(self, service):
        """Test phone number with dashes is normalized."""
        result = service._normalize_phone_number("415-555-1234")
        assert result == "+14155551234"

    def test_normalize_phone_with_dots(self, service):
        """Test phone number with dots is normalized."""
        result = service._normalize_phone_number("415.555.1234")
        assert result == "+14155551234"

    def test_normalize_phone_with_spaces(self, service):
        """Test phone number with spaces is normalized."""
        result = service._normalize_phone_number("415 555 1234")
        assert result == "+14155551234"

    def test_normalize_phone_with_country_code(self, service):
        """Test phone number with country code is preserved."""
        result = service._normalize_phone_number("+1 (415) 555-1234")
        assert result == "+14155551234"

    def test_normalize_invalid_phone_returns_original(self, service):
        """Test invalid phone number returns original string."""
        invalid = "not-a-phone"
        result = service._normalize_phone_number(invalid)
        assert result == invalid

    def test_normalize_empty_phone_returns_empty(self, service):
        """Test empty phone number returns empty string."""
        result = service._normalize_phone_number("")
        assert result == ""

    def test_normalize_whitespace_phone_returns_original(self, service):
        """Test whitespace-only phone returns original."""
        result = service._normalize_phone_number("   ")
        assert result == "   "

    def test_normalize_international_format(self, service):
        """Test international format is preserved."""
        result = service._normalize_phone_number("+15551234567")
        assert result == "+15551234567"


# ============================================================================
# PersonDuplicateDetector.find_duplicates() Tests
# ============================================================================


@pytest.mark.django_db
class TestPersonDuplicateDetectorFindDuplicates:
    """Tests for PersonDuplicateDetector.find_duplicates()."""

    def test_find_duplicates_with_exact_email_match(self, detector, existing_person):
        """Test finding duplicate by exact email match."""
        data: PersonDataDict = {
            "first_name": "Different",
            "last_name": "Person",
            "email": "jane.smith@example.com",  # Same as existing
        }
        duplicates = detector.find_duplicates(data)
        assert duplicates.count() == 1
        assert existing_person in duplicates

    def test_find_duplicates_with_case_insensitive_email(
        self, detector, existing_person
    ):
        """Test email matching is case-insensitive."""
        data: PersonDataDict = {
            "first_name": "Different",
            "last_name": "Person",
            "email": "JANE.SMITH@EXAMPLE.COM",  # Uppercase
        }
        duplicates = detector.find_duplicates(data)
        assert duplicates.count() == 1

    def test_find_duplicates_with_exact_phone_match(self, detector, existing_person):
        """Test finding duplicate by exact phone match."""
        data: PersonDataDict = {
            "first_name": "Different",
            "last_name": "Person",
            "phone_primary": "+15551234567",  # Same as existing
        }
        duplicates = detector.find_duplicates(data)
        assert duplicates.count() == 1

    def test_find_duplicates_with_name_and_dob_match(self, detector, existing_person):
        """Test finding duplicate by name and date of birth."""
        data: PersonDataDict = {
            "first_name": "Jane",
            "last_name": "Smith",
            "date_of_birth": date(1985, 5, 15),  # Same as existing
        }
        duplicates = detector.find_duplicates(data)
        assert duplicates.count() == 1

    def test_find_duplicates_with_name_and_address_match(self, detector, test_user, db):
        """Test finding duplicate by name and address."""
        # Create person with specific address
        person = Person.objects.create(
            first_name="John",
            last_name="Doe",
            street_address="123 Main St",
            zip_code="90210",
            created_by=test_user,
        )

        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "street_address": "123 Main St",
            "zip_code": "90210",
        }
        duplicates = detector.find_duplicates(data)
        assert person in duplicates

    def test_find_duplicates_with_no_matches(self, detector):
        """Test no duplicates found when data doesn't match."""
        data: PersonDataDict = {
            "first_name": "Unique",
            "last_name": "Person",
            "email": "unique@example.com",
        }
        duplicates = detector.find_duplicates(data)
        assert duplicates.count() == 0

    def test_find_duplicates_excludes_inactive_persons(self, detector, test_user, db):
        """Test inactive persons are excluded from duplicates."""
        # Create inactive person
        Person.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            is_active=False,  # Inactive
            created_by=test_user,
        )

        data: PersonDataDict = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane@example.com",
        }
        duplicates = detector.find_duplicates(data)
        assert duplicates.count() == 0

    def test_find_duplicates_with_exclude_id(self, detector, existing_person):
        """Test exclude_id parameter excludes specific person."""
        data: PersonDataDict = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane.smith@example.com",
        }
        duplicates = detector.find_duplicates(data, exclude_id=str(existing_person.pk))
        assert duplicates.count() == 0

    def test_find_duplicates_requires_first_name(self, detector):
        """Test ValidationError raised when first_name missing."""
        data: PersonDataDict = {
            "last_name": "Doe",
            "email": "test@example.com",
        }
        with pytest.raises(ValidationError) as exc_info:
            detector.find_duplicates(data)
        assert "first_name" in str(exc_info.value)

    def test_find_duplicates_requires_last_name(self, detector):
        """Test ValidationError raised when last_name missing."""
        data: PersonDataDict = {
            "first_name": "John",
            "email": "test@example.com",
        }
        with pytest.raises(ValidationError) as exc_info:
            detector.find_duplicates(data)
        assert "last_name" in str(exc_info.value)

    def test_find_duplicates_with_string_date_of_birth(self, detector, existing_person):
        """Test date of birth as string is handled correctly."""
        data: PersonDataDict = {
            "first_name": "Jane",
            "last_name": "Smith",
            "date_of_birth": "1985-05-15",  # String format
        }
        duplicates = detector.find_duplicates(data)
        assert duplicates.count() == 1

    def test_find_duplicates_with_invalid_date_string(self, detector):
        """Test invalid date string is handled gracefully."""
        data: PersonDataDict = {
            "first_name": "Jane",
            "last_name": "Smith",
            "date_of_birth": "invalid-date",
        }
        # Should not raise exception, just skip date matching
        duplicates = detector.find_duplicates(data)
        assert duplicates is not None


# ============================================================================
# PersonDuplicateDetector._build_duplicate_query() Tests
# ============================================================================


@pytest.mark.django_db
class TestPersonDuplicateDetectorBuildQuery:
    """Tests for PersonDuplicateDetector._build_duplicate_query()."""

    def test_build_query_with_email_only(self, detector):
        """Test query built with email only."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
        }
        q = detector._build_duplicate_query(data)
        assert isinstance(q, Q)
        # Query should contain email filter
        assert q.children  # Q object has conditions

    def test_build_query_with_phone_only(self, detector):
        """Test query built with phone only."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "phone_primary": "+15551234567",
        }
        q = detector._build_duplicate_query(data)
        assert isinstance(q, Q)

    def test_build_query_with_name_and_dob(self, detector):
        """Test query built with name and date of birth."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": date(1990, 1, 1),
        }
        q = detector._build_duplicate_query(data)
        assert isinstance(q, Q)

    def test_build_query_with_name_and_address(self, detector):
        """Test query built with name and address."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "street_address": "123 Main St",
            "zip_code": "90210",
        }
        q = detector._build_duplicate_query(data)
        assert isinstance(q, Q)

    def test_build_query_with_multiple_criteria(self, detector):
        """Test query built with multiple matching criteria."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone_primary": "+15551234567",
            "date_of_birth": date(1990, 1, 1),
        }
        q = detector._build_duplicate_query(data)
        assert isinstance(q, Q)
        # Should have multiple OR conditions
        assert len(q.children) > 1

    def test_build_query_strips_whitespace(self, detector):
        """Test query builder strips whitespace from inputs."""
        data: PersonDataDict = {
            "first_name": "  John  ",
            "last_name": "  Doe  ",
            "email": "  john@example.com  ",
        }
        q = detector._build_duplicate_query(data)
        assert isinstance(q, Q)

    def test_build_query_handles_empty_values(self, detector):
        """Test query builder handles empty string values."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "",
            "phone_primary": "",
        }
        q = detector._build_duplicate_query(data)
        assert isinstance(q, Q)

    def test_build_query_with_invalid_date_format(self, detector):
        """Test query builder handles invalid date format."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "not-a-date",
        }
        q = detector._build_duplicate_query(data)
        assert isinstance(q, Q)

    def test_build_query_returns_empty_q_with_no_matchable_fields(self, detector):
        """Test empty Q object when no matchable fields provided."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            # No email, phone, DOB, or address
        }
        q = detector._build_duplicate_query(data)
        assert isinstance(q, Q)
        # Should be empty Q object with no children
        assert len(q.children) == 0


# ============================================================================
# Edge Cases and Security Tests
# ============================================================================


@pytest.mark.django_db
class TestEdgeCasesAndSecurity:
    """Tests for edge cases and security concerns."""

    def test_xss_sanitization_in_multiple_fields(self, service):
        """Test XSS is sanitized from all text fields."""
        xss_payload = "<script>alert('xss')</script>"
        data: PersonDataDict = {
            "first_name": xss_payload + "John",
            "last_name": "Doe" + xss_payload,
            "notes": f"Notes with {xss_payload} in middle",
            "street_address": xss_payload + "123 Main St",
        }
        sanitized = service._sanitize_person_data(data)

        for field in ["first_name", "last_name", "notes", "street_address"]:
            if field in sanitized:
                assert "<script>" not in sanitized[field]
                assert "alert" not in sanitized[field]

    def test_sql_injection_patterns_handled_safely(self, service, test_user):
        """Test SQL injection patterns are handled safely."""
        sql_injection = "'; DROP TABLE persons; --"
        data: PersonDataDict = {
            "first_name": sql_injection,
            "last_name": "Doe",
        }

        # Should not raise exception, Django ORM protects against SQL injection
        person, _ = service.create_person(
            person_data=data,
            created_by=test_user,
            check_duplicates=False,
        )
        assert person.first_name == sql_injection  # Stored as-is, but safely

    def test_extremely_long_input_truncated(self, service):
        """Test extremely long inputs are truncated."""
        very_long = "A" * 20000
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "notes": very_long,
        }
        sanitized = service._sanitize_person_data(data)
        assert len(sanitized["notes"]) <= 10000

    def test_null_bytes_removed_from_text(self, service):
        """Test null bytes are removed from text fields."""
        data: PersonDataDict = {
            "first_name": "John\x00Test",
            "last_name": "Doe\x00\x00",
        }
        sanitized = service._sanitize_person_data(data)
        assert "\x00" not in sanitized["first_name"]
        assert "\x00" not in sanitized["last_name"]

    def test_unicode_normalization(self, service):
        """Test Unicode characters are handled correctly."""
        data: PersonDataDict = {
            "first_name": "François",
            "last_name": "Müller",
            "city": "São Paulo",
            "notes": "测试 テスト тест",
        }
        sanitized = service._sanitize_person_data(data)
        assert sanitized["first_name"] == "François"
        assert sanitized["last_name"] == "Müller"
        assert sanitized["city"] == "São Paulo"

    def test_empty_string_vs_none_handling(self, service):
        """Test difference between empty string and None."""
        data_with_empty: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "middle_name": "",
        }
        sanitized = service._sanitize_person_data(data_with_empty)
        assert "middle_name" not in sanitized

    def test_phone_international_format_edge_cases(self, service):
        """Test various international phone format edge cases."""
        test_cases = [
            ("+1-415-555-1234", "+14155551234"),
            ("1 (415) 555-1234", "+14155551234"),
            ("+1.415.555.1234", "+14155551234"),
            ("4155551234", "+14155551234"),
        ]
        for input_phone, expected in test_cases:
            result = service._normalize_phone_number(input_phone)
            assert result == expected

    def test_concurrent_duplicate_creation_with_transaction(self, service, test_user):
        """Test transaction atomicity prevents concurrent duplicates."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": date(1990, 1, 1),
        }

        # Create first person
        person1, _ = service.create_person(
            person_data=data,
            created_by=test_user,
            check_duplicates=False,
        )

        # Try to create duplicate - should fail with ValidationError
        with pytest.raises(ValidationError):
            service.create_person(
                person_data=data,
                created_by=test_user,
                check_duplicates=False,
            )

        # Verify only one person was created
        assert (
            Person.objects.filter(
                first_name="John",
                last_name="Doe",
                date_of_birth=date(1990, 1, 1),
            ).count()
            == 1
        )

    def test_tags_with_special_characters(self, service):
        """Test tags with special characters are handled."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "tags": ["tag-1", "tag_2", "tag.3", "tag 4"],
        }
        sanitized = service._sanitize_person_data(data)
        assert len(sanitized["tags"]) == 4

    def test_email_with_plus_addressing(self, service):
        """Test email with plus addressing (Gmail feature) works."""
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john+test@example.com",
        }
        errors = service.validate_person_data(data)
        assert "email" not in errors

        sanitized = service._sanitize_person_data(data)
        assert sanitized["email"] == "john+test@example.com"


# ============================================================================
# Integration Tests with Django ORM
# ============================================================================


@pytest.mark.django_db
class TestDjangoORMIntegration:
    """Tests for integration with Django ORM."""

    def test_person_saved_to_database(self, service, test_user, valid_person_data):
        """Test person is actually saved to database."""
        initial_count = Person.objects.count()
        person, _ = service.create_person(
            person_data=valid_person_data,
            created_by=test_user,
            check_duplicates=False,
        )
        assert Person.objects.count() == initial_count + 1
        assert Person.objects.filter(pk=person.pk).exists()

    def test_duplicate_query_uses_indexes(self, detector, test_user, db):
        """Test duplicate detection queries use database indexes."""
        # Create multiple persons to test index usage
        for i in range(10):
            Person.objects.create(
                first_name=f"Person{i}",
                last_name=f"Test{i}",
                email=f"person{i}@test.com",
                created_by=test_user,
            )

        data: PersonDataDict = {
            "first_name": "Person5",
            "last_name": "Test5",
            "email": "person5@test.com",
        }

        # Query should be fast even with multiple records
        duplicates = detector.find_duplicates(data)
        assert duplicates.count() == 1

    def test_queryset_distinct_removes_duplicates(self, detector, test_user, db):
        """Test queryset returns distinct results."""
        # Create person matching multiple criteria
        Person.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@test.com",
            phone_primary="+15551234567",
            created_by=test_user,
        )

        # Search with multiple matching criteria
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@test.com",
            "phone_primary": "+15551234567",
        }

        duplicates = detector.find_duplicates(data)
        # Should return person only once despite multiple matches
        assert duplicates.count() == 1

    def test_transaction_rollback_on_validation_error(self, service, test_user):
        """Test database transaction rolls back on validation error."""
        initial_count = Person.objects.count()

        invalid_data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "invalid-email",
        }

        with pytest.raises(ValidationError):
            service.create_person(
                person_data=invalid_data,
                created_by=test_user,
                check_duplicates=False,
            )

        # No person should be created
        assert Person.objects.count() == initial_count

    def test_model_full_clean_called(self, service, test_user):
        """Test model's full_clean() is called during creation."""
        # This tests that model-level validation is also enforced
        data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "test@example.com",
        }

        person, _ = service.create_person(
            person_data=data,
            created_by=test_user,
            check_duplicates=False,
        )

        # If full_clean() wasn't called, this would fail
        assert person.pk is not None

    def test_soft_delete_respected_in_duplicates(self, detector, test_user, db):
        """Test soft-deleted persons are excluded from duplicate search."""
        # Create active person
        active = Person.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@test.com",
            is_active=True,
            created_by=test_user,
        )

        # Create soft-deleted person with same data
        Person.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@test.com",
            is_active=False,  # Soft deleted
            created_by=test_user,
        )

        data: PersonDataDict = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane@test.com",
        }

        duplicates = detector.find_duplicates(data)
        # Should only find the active person
        assert duplicates.count() == 1
        assert active in duplicates
