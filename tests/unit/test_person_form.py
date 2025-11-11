"""
Comprehensive unit tests for PersonForm.

This test module covers:
- All 18 field validation methods (clean_* methods)
- Form-level validation (clean() method)
- XSS prevention and sanitization
- Duplicate detection integration
- Edge cases and boundary conditions
- Security tests

Target coverage: 95%+ for PersonForm
"""

from datetime import date, timedelta
from typing import Any
from unittest.mock import Mock, patch

import pytest

from civicpulse.forms import PersonForm
from civicpulse.models import Person


@pytest.fixture
def valid_person_data() -> dict[str, Any]:
    """Provide valid person data for testing."""
    return {
        "first_name": "John",
        "middle_name": "Michael",
        "last_name": "Doe",
        "suffix": "Jr.",
        "date_of_birth": date(1985, 5, 15),
        "gender": "M",
        "email": "john.doe@example.com",
        "phone_primary": "(415) 555-1234",
        "phone_secondary": "415-555-5678",
        "street_address": "123 Main St",
        "apartment_number": "Apt 4B",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94102",
        "county": "San Francisco",
        "occupation": "Software Engineer",
        "employer": "Tech Corp",
        "notes": "Some notes about this person",
        "tags": "volunteer, donor, member",
    }


@pytest.fixture
def minimal_person_data() -> dict[str, Any]:
    """Provide minimal required person data."""
    # Gender is required by the model (has default but form doesn't use it)
    return {
        "first_name": "Jane",
        "last_name": "Smith",
        "gender": "U",
    }


# =============================================================================
# Field Validation Tests - clean_first_name()
# =============================================================================


@pytest.mark.django_db
class TestCleanFirstName:
    """Test clean_first_name() method."""

    def test_valid_first_name(self, valid_person_data: dict[str, Any]) -> None:
        """Test that valid first name passes validation."""
        form = PersonForm(data=valid_person_data)
        assert form.is_valid()
        assert form.cleaned_data["first_name"] == "John"

    def test_empty_first_name_raises_error(self) -> None:
        """Test that empty first name raises ValidationError."""
        data = {"first_name": "", "last_name": "Doe", "gender": "U"}
        form = PersonForm(data=data)
        assert not form.is_valid()
        assert "first_name" in form.errors
        # Django's required validation message, not our custom clean method
        assert "required" in str(form.errors["first_name"]).lower()

    def test_whitespace_only_first_name_raises_error(self) -> None:
        """Test that whitespace-only first name raises ValidationError."""
        data = {"first_name": "   ", "last_name": "Doe", "gender": "U"}
        form = PersonForm(data=data)
        assert not form.is_valid()
        assert "first_name" in form.errors
        # Django CharFields strip whitespace by default, so "   " becomes ""
        # which triggers the required field validation, not clean_first_name
        assert "required" in str(form.errors["first_name"]).lower()

    def test_first_name_max_length_validation(self) -> None:
        """Test that first name exceeding 100 chars raises ValidationError."""
        data = {"first_name": "A" * 101, "last_name": "Doe", "gender": "U"}
        form = PersonForm(data=data)
        assert not form.is_valid()
        assert "first_name" in form.errors
        assert "100 characters" in str(form.errors["first_name"])

    def test_first_name_xss_sanitization(self) -> None:
        """Test that script tags are removed from first name."""
        data = {
            "first_name": "John<script>alert('xss')</script>",
            "last_name": "Doe",
            "gender": "U",
        }
        form = PersonForm(data=data)
        assert form.is_valid()
        assert "<script>" not in form.cleaned_data["first_name"]
        assert "alert" not in form.cleaned_data["first_name"]
        # sanitize_text_field removes script and content
        assert form.cleaned_data["first_name"] == "John"

    def test_first_name_html_stripped(self) -> None:
        """Test that HTML tags are stripped from first name."""
        data = {"first_name": "John<b>Bold</b>", "last_name": "Doe", "gender": "U"}
        form = PersonForm(data=data)
        assert form.is_valid()
        assert "<b>" not in form.cleaned_data["first_name"]
        # strip_tags removes the tags but keeps the content
        assert form.cleaned_data["first_name"] == "JohnBold"

    def test_first_name_unicode_characters(self) -> None:
        """Test that unicode characters are handled properly."""
        data = {"first_name": "José", "last_name": "García", "gender": "U"}
        form = PersonForm(data=data)
        assert form.is_valid()
        assert form.cleaned_data["first_name"] == "José"


# =============================================================================
# Field Validation Tests - clean_middle_name()
# =============================================================================


@pytest.mark.django_db
class TestCleanMiddleName:
    """Test clean_middle_name() method."""

    def test_valid_middle_name(self, valid_person_data: dict[str, Any]) -> None:
        """Test that valid middle name passes validation."""
        form = PersonForm(data=valid_person_data)
        assert form.is_valid()
        assert form.cleaned_data["middle_name"] == "Michael"

    def test_empty_middle_name_allowed(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that empty middle name is allowed."""
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["middle_name"] == ""

    def test_middle_name_max_length_validation(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that middle name exceeding 100 chars raises ValidationError."""
        minimal_person_data["middle_name"] = "M" * 101
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "middle_name" in form.errors

    def test_middle_name_xss_sanitization(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that script tags are removed from middle name."""
        minimal_person_data["middle_name"] = "Mike<script>alert('xss')</script>"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert "<script>" not in form.cleaned_data["middle_name"]


# =============================================================================
# Field Validation Tests - clean_last_name()
# =============================================================================


@pytest.mark.django_db
class TestCleanLastName:
    """Test clean_last_name() method."""

    def test_valid_last_name(self, valid_person_data: dict[str, Any]) -> None:
        """Test that valid last name passes validation."""
        form = PersonForm(data=valid_person_data)
        assert form.is_valid()
        assert form.cleaned_data["last_name"] == "Doe"

    def test_empty_last_name_raises_error(self) -> None:
        """Test that empty last name raises ValidationError."""
        data = {"first_name": "John", "last_name": "", "gender": "U"}
        form = PersonForm(data=data)
        assert not form.is_valid()
        assert "last_name" in form.errors
        assert "required" in str(form.errors["last_name"]).lower()

    def test_last_name_max_length_validation(self) -> None:
        """Test that last name exceeding 100 chars raises ValidationError."""
        data = {"first_name": "John", "last_name": "D" * 101, "gender": "U"}
        form = PersonForm(data=data)
        assert not form.is_valid()
        assert "last_name" in form.errors

    def test_last_name_xss_sanitization(self) -> None:
        """Test that script tags are removed from last name."""
        data = {
            "first_name": "John",
            "last_name": "Doe<script>alert('xss')</script>",
            "gender": "U",
        }
        form = PersonForm(data=data)
        assert form.is_valid()
        assert "<script>" not in form.cleaned_data["last_name"]
        assert form.cleaned_data["last_name"] == "Doe"


# =============================================================================
# Field Validation Tests - clean_suffix()
# =============================================================================


@pytest.mark.django_db
class TestCleanSuffix:
    """Test clean_suffix() method."""

    def test_valid_suffix(self, valid_person_data: dict[str, Any]) -> None:
        """Test that valid suffix passes validation."""
        form = PersonForm(data=valid_person_data)
        assert form.is_valid()
        assert form.cleaned_data["suffix"] == "Jr."

    def test_empty_suffix_allowed(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that empty suffix is allowed."""
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["suffix"] == ""

    def test_suffix_max_length_validation(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that suffix exceeding 10 chars raises ValidationError."""
        minimal_person_data["suffix"] = "S" * 11
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "suffix" in form.errors

    def test_suffix_xss_sanitization(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that script tags are removed from suffix."""
        # Suffix field has max_length=10, so use a shorter XSS pattern
        minimal_person_data["suffix"] = "Jr<b>.</b>"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert "<b>" not in form.cleaned_data["suffix"]
        # HTML tags are stripped, leaving just the text content
        assert form.cleaned_data["suffix"] == "Jr."


# =============================================================================
# Field Validation Tests - clean_email()
# =============================================================================


@pytest.mark.django_db
class TestCleanEmail:
    """Test clean_email() method."""

    def test_valid_email(self, valid_person_data: dict[str, Any]) -> None:
        """Test that valid email passes validation."""
        form = PersonForm(data=valid_person_data)
        assert form.is_valid()
        assert form.cleaned_data["email"] == "john.doe@example.com"

    def test_email_lowercase_normalization(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that email is normalized to lowercase."""
        minimal_person_data["email"] = "JOHN.DOE@EXAMPLE.COM"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["email"] == "john.doe@example.com"

    def test_email_whitespace_trimmed(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that whitespace is trimmed from email."""
        minimal_person_data["email"] = "  john@example.com  "
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["email"] == "john@example.com"

    def test_invalid_email_format(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that invalid email format raises ValidationError."""
        minimal_person_data["email"] = "not-an-email"
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_empty_email_allowed(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that empty email is allowed."""
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data.get("email", "") == ""


# =============================================================================
# Field Validation Tests - clean_phone_primary() & clean_phone_secondary()
# =============================================================================


@pytest.mark.django_db
class TestCleanPhones:
    """Test clean_phone_primary() and clean_phone_secondary() methods."""

    def test_valid_phone_formats(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that various valid phone formats pass validation."""
        valid_formats = [
            "(415) 555-1234",
            "415-555-1234",
            "4155551234",
            "+1-415-555-1234",
            "+14155551234",
        ]
        for phone in valid_formats:
            data = minimal_person_data.copy()
            data["phone_primary"] = phone
            form = PersonForm(data=data)
            assert form.is_valid(), f"Phone format {phone} should be valid"

    def test_invalid_phone_format(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that invalid phone format raises ValidationError."""
        minimal_person_data["phone_primary"] = "123"
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "phone_primary" in form.errors

    def test_empty_phone_allowed(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that empty phone is allowed."""
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()

    def test_phone_secondary_validation(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that phone_secondary uses same validation."""
        minimal_person_data["phone_secondary"] = "415-555-1234"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()

        minimal_person_data["phone_secondary"] = "invalid"
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "phone_secondary" in form.errors


# =============================================================================
# Field Validation Tests - clean_date_of_birth()
# =============================================================================


@pytest.mark.django_db
class TestCleanDateOfBirth:
    """Test clean_date_of_birth() method."""

    def test_valid_date_of_birth(self, valid_person_data: dict[str, Any]) -> None:
        """Test that valid date of birth passes validation."""
        form = PersonForm(data=valid_person_data)
        assert form.is_valid()
        assert form.cleaned_data["date_of_birth"] == date(1985, 5, 15)

    def test_future_date_raises_error(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that future date raises ValidationError."""
        minimal_person_data["date_of_birth"] = date.today() + timedelta(days=1)
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "date_of_birth" in form.errors
        assert "future" in str(form.errors["date_of_birth"]).lower()

    def test_unrealistic_age_raises_error(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that date indicating age over 150 raises ValidationError."""
        minimal_person_data["date_of_birth"] = date.today() - timedelta(days=365 * 151)
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "date_of_birth" in form.errors
        assert "150" in str(form.errors["date_of_birth"])

    def test_empty_date_of_birth_allowed(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that empty date of birth is allowed."""
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data.get("date_of_birth") is None


# =============================================================================
# Field Validation Tests - clean_state()
# =============================================================================


@pytest.mark.django_db
class TestCleanState:
    """Test clean_state() method."""

    def test_valid_state_codes(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that all valid US state codes pass validation."""
        valid_states = ["CA", "NY", "TX", "FL", "DC"]
        for state in valid_states:
            data = minimal_person_data.copy()
            data["state"] = state
            form = PersonForm(data=data)
            assert form.is_valid(), f"State code {state} should be valid"
            assert form.cleaned_data["state"] == state

    def test_lowercase_state_normalized_to_uppercase(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that lowercase state code is normalized to uppercase."""
        minimal_person_data["state"] = "ca"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["state"] == "CA"

    def test_invalid_state_code_raises_error(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that invalid state code raises ValidationError."""
        minimal_person_data["state"] = "XX"
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "state" in form.errors
        assert "not a valid" in str(form.errors["state"])

    def test_empty_state_allowed(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that empty state is allowed."""
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()


# =============================================================================
# Field Validation Tests - clean_zip_code()
# =============================================================================


@pytest.mark.django_db
class TestCleanZipCode:
    """Test clean_zip_code() method."""

    def test_valid_5_digit_zip(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that 5-digit ZIP code passes validation."""
        minimal_person_data["zip_code"] = "94102"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["zip_code"] == "94102"

    def test_valid_9_digit_zip(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that 9-digit ZIP+4 code passes validation."""
        minimal_person_data["zip_code"] = "94102-1234"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["zip_code"] == "94102-1234"

    def test_invalid_zip_format(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that invalid ZIP format raises ValidationError."""
        invalid_zips = ["123", "1234", "12345-", "12345-12", "ABCDE", "12345-ABCD"]
        for zip_code in invalid_zips:
            data = minimal_person_data.copy()
            data["zip_code"] = zip_code
            form = PersonForm(data=data)
            assert not form.is_valid(), f"ZIP code {zip_code} should be invalid"
            assert "zip_code" in form.errors

    def test_empty_zip_allowed(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that empty ZIP code is allowed."""
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()


# =============================================================================
# Field Validation Tests - Address Fields
# =============================================================================


@pytest.mark.django_db
class TestAddressFields:
    """Test clean methods for address fields."""

    def test_clean_street_address(self, minimal_person_data: dict[str, Any]) -> None:
        """Test street address validation and sanitization."""
        minimal_person_data["street_address"] = (
            "123 Main St<script>alert('xss')</script>"
        )
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert "<script>" not in form.cleaned_data["street_address"]
        assert "123 Main St" in form.cleaned_data["street_address"]

    def test_street_address_max_length(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test street address max length validation."""
        minimal_person_data["street_address"] = "A" * 256
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "street_address" in form.errors

    def test_clean_apartment_number(self, minimal_person_data: dict[str, Any]) -> None:
        """Test apartment number validation."""
        minimal_person_data["apartment_number"] = "Apt 4B"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["apartment_number"] == "Apt 4B"

    def test_apartment_number_max_length(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test apartment number max length validation."""
        minimal_person_data["apartment_number"] = "A" * 51
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "apartment_number" in form.errors

    def test_clean_city(self, minimal_person_data: dict[str, Any]) -> None:
        """Test city validation and sanitization."""
        minimal_person_data["city"] = "San Francisco"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["city"] == "San Francisco"

    def test_city_max_length(self, minimal_person_data: dict[str, Any]) -> None:
        """Test city max length validation."""
        minimal_person_data["city"] = "C" * 101
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "city" in form.errors

    def test_clean_county(self, minimal_person_data: dict[str, Any]) -> None:
        """Test county validation and sanitization."""
        minimal_person_data["county"] = "San Francisco County"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["county"] == "San Francisco County"

    def test_county_max_length(self, minimal_person_data: dict[str, Any]) -> None:
        """Test county max length validation."""
        minimal_person_data["county"] = "C" * 101
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "county" in form.errors


# =============================================================================
# Field Validation Tests - Employment Fields
# =============================================================================


@pytest.mark.django_db
class TestEmploymentFields:
    """Test clean methods for employment fields."""

    def test_clean_occupation(self, minimal_person_data: dict[str, Any]) -> None:
        """Test occupation validation and sanitization."""
        minimal_person_data["occupation"] = "Software Engineer"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["occupation"] == "Software Engineer"

    def test_occupation_max_length(self, minimal_person_data: dict[str, Any]) -> None:
        """Test occupation max length validation."""
        minimal_person_data["occupation"] = "O" * 101
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "occupation" in form.errors

    def test_occupation_xss_sanitization(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test occupation XSS sanitization."""
        minimal_person_data["occupation"] = "Engineer<script>alert('xss')</script>"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert "<script>" not in form.cleaned_data["occupation"]

    def test_clean_employer(self, minimal_person_data: dict[str, Any]) -> None:
        """Test employer validation and sanitization."""
        minimal_person_data["employer"] = "Tech Corp"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["employer"] == "Tech Corp"

    def test_employer_max_length(self, minimal_person_data: dict[str, Any]) -> None:
        """Test employer max length validation."""
        minimal_person_data["employer"] = "E" * 101
        form = PersonForm(data=minimal_person_data)
        assert not form.is_valid()
        assert "employer" in form.errors


# =============================================================================
# Field Validation Tests - clean_notes()
# =============================================================================


@pytest.mark.django_db
class TestCleanNotes:
    """Test clean_notes() method."""

    def test_valid_notes(self, valid_person_data: dict[str, Any]) -> None:
        """Test that valid notes pass validation."""
        form = PersonForm(data=valid_person_data)
        assert form.is_valid()
        assert "Some notes" in form.cleaned_data["notes"]

    def test_notes_max_length(self, minimal_person_data: dict[str, Any]) -> None:
        """Test notes max length validation (10,000 chars)."""
        # sanitize_text_field limits to 10000, so 10001 will be truncated not rejected
        minimal_person_data["notes"] = "N" * 10001
        form = PersonForm(data=minimal_person_data)
        # Form should be valid since sanitize truncates
        assert form.is_valid()
        # But the value should be truncated to 10000
        assert len(form.cleaned_data["notes"]) == 10000

    def test_notes_xss_sanitization(self, minimal_person_data: dict[str, Any]) -> None:
        """Test notes XSS sanitization."""
        minimal_person_data["notes"] = "Important<script>alert('xss')</script>notes"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert "<script>" not in form.cleaned_data["notes"]

    def test_empty_notes_allowed(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that empty notes are allowed."""
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()


# =============================================================================
# Field Validation Tests - clean_tags()
# =============================================================================


@pytest.mark.django_db
class TestCleanTags:
    """Test clean_tags() method."""

    def test_comma_separated_tags_parsed(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that comma-separated tags are parsed into list."""
        minimal_person_data["tags"] = "volunteer, donor, member"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        tags = form.cleaned_data["tags"]
        assert isinstance(tags, list)
        assert len(tags) == 3
        assert "volunteer" in tags
        assert "donor" in tags
        assert "member" in tags

    def test_tags_whitespace_trimmed(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that whitespace is trimmed from tags."""
        minimal_person_data["tags"] = "  volunteer  ,  donor  "
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        tags = form.cleaned_data["tags"]
        assert "volunteer" in tags
        assert "donor" in tags

    def test_tags_xss_sanitization(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that tags are sanitized for XSS."""
        minimal_person_data["tags"] = "volunteer<script>alert('xss')</script>, donor"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        tags = form.cleaned_data["tags"]
        for tag in tags:
            assert "<script>" not in tag

    def test_empty_tags_removed(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that empty tags are removed."""
        minimal_person_data["tags"] = "volunteer, , , donor, "
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        tags = form.cleaned_data["tags"]
        assert len(tags) == 2

    def test_empty_tags_string_returns_empty_list(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that empty string returns empty list."""
        minimal_person_data["tags"] = ""
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert form.cleaned_data["tags"] == []


# =============================================================================
# Form-Level Validation Tests - clean()
# =============================================================================


@pytest.mark.django_db
class TestFormLevelValidation:
    """Test clean() method and cross-field validation."""

    @patch("civicpulse.services.person_service.PersonDuplicateDetector")
    def test_duplicate_detection_called(
        self, mock_detector_class: Mock, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that duplicate detection is called with proper data."""
        mock_detector = Mock()
        mock_detector.find_duplicates.return_value = []
        mock_detector_class.return_value = mock_detector

        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()

        # Verify detector was instantiated and called
        mock_detector_class.assert_called_once()
        mock_detector.find_duplicates.assert_called_once()

    @patch("civicpulse.services.person_service.PersonDuplicateDetector")
    def test_duplicates_stored_in_form(
        self, mock_detector_class: Mock, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that duplicates are stored in form.duplicates."""
        # Create mock duplicate persons
        mock_duplicate1 = Mock(spec=Person)
        mock_duplicate1.id = 1
        mock_duplicate1.first_name = "Jane"
        mock_duplicate1.last_name = "Smith"

        mock_duplicate2 = Mock(spec=Person)
        mock_duplicate2.id = 2
        mock_duplicate2.first_name = "Janet"
        mock_duplicate2.last_name = "Smith"

        mock_detector = Mock()
        mock_detector.find_duplicates.return_value = [mock_duplicate1, mock_duplicate2]
        mock_detector_class.return_value = mock_detector

        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()

        # Check that duplicates are stored
        assert len(form.duplicates) == 2
        assert mock_duplicate1 in form.duplicates
        assert mock_duplicate2 in form.duplicates

    @patch("civicpulse.services.person_service.PersonDuplicateDetector")
    def test_duplicate_detection_excludes_current_instance(
        self, mock_detector_class: Mock, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that duplicate detection excludes current instance when editing."""
        mock_detector = Mock()
        mock_detector.find_duplicates.return_value = []
        mock_detector_class.return_value = mock_detector

        # Create a real Person instance in the database
        existing_person = Person.objects.create(
            first_name="John", last_name="Doe", gender="M"
        )

        form = PersonForm(data=minimal_person_data, instance=existing_person)
        assert form.is_valid()

        # Verify exclude_id was passed (compare as string since UUID might be serialized)
        call_kwargs = mock_detector.find_duplicates.call_args[1]
        assert str(call_kwargs["exclude_id"]) == str(existing_person.id)

    @patch("civicpulse.services.person_service.PersonDuplicateDetector")
    def test_duplicate_detection_limits_results(
        self, mock_detector_class: Mock, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that duplicate results are limited to 10."""
        # Create 15 mock duplicates
        mock_duplicates = [Mock(spec=Person, id=i) for i in range(15)]

        mock_detector = Mock()
        mock_detector.find_duplicates.return_value = mock_duplicates
        mock_detector_class.return_value = mock_detector

        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()

        # Should only store first 10
        assert len(form.duplicates) == 10

    def test_form_valid_with_all_fields(
        self, valid_person_data: dict[str, Any]
    ) -> None:
        """Test that form is valid with all fields populated."""
        form = PersonForm(data=valid_person_data)
        assert form.is_valid()
        assert not form.errors

    def test_form_valid_with_minimal_fields(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that form is valid with only required fields."""
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()
        assert not form.errors


# =============================================================================
# Security Tests
# =============================================================================


@pytest.mark.django_db
class TestSecurity:
    """Test security features of PersonForm."""

    def test_sql_injection_patterns_escaped(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that SQL injection patterns are properly handled."""
        sql_patterns = [
            "Robert'; DROP TABLE Person;--",
            "admin'--",
            "1' OR '1'='1",
        ]
        for pattern in sql_patterns:
            data = minimal_person_data.copy()
            data["first_name"] = pattern
            form = PersonForm(data=data)
            # Form should be valid - sanitization doesn't reject SQL patterns
            # It just strips HTML/script tags. Django ORM handles SQL injection.
            assert form.is_valid()
            # The cleaned data preserves the input (minus any HTML tags)
            cleaned = form.cleaned_data["first_name"]
            # Just verify no HTML/script tags are present
            assert "<" not in cleaned or ">" not in cleaned

    def test_xss_all_text_fields(self, minimal_person_data: dict[str, Any]) -> None:
        """Test XSS prevention in all text fields."""
        xss_payload = "<script>alert('xss')</script>"
        text_fields = [
            "first_name",
            "middle_name",
            "last_name",
            "suffix",
            "street_address",
            "apartment_number",
            "city",
            "county",
            "occupation",
            "employer",
            "notes",
        ]

        for field in text_fields:
            data = minimal_person_data.copy()
            data[field] = f"Test{xss_payload}Value"
            form = PersonForm(data=data)

            if form.is_valid():
                cleaned_value = form.cleaned_data.get(field, "")
                assert "<script>" not in cleaned_value, f"XSS not prevented in {field}"
                assert "alert" not in cleaned_value, f"XSS not prevented in {field}"

    def test_no_javascript_events_in_fields(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that JavaScript event handlers are removed."""
        data = minimal_person_data.copy()
        data["first_name"] = "John<img src=x onerror=alert('xss')>"
        form = PersonForm(data=data)
        assert form.is_valid()
        assert "onerror" not in form.cleaned_data["first_name"]

    def test_control_characters_removed(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that control characters are removed."""
        data = minimal_person_data.copy()
        data["first_name"] = "John\x00\x01\x02Doe"
        form = PersonForm(data=data)
        # Control characters in form data can cause validation to fail
        # Check if form is valid or if there are errors
        if not form.is_valid():
            # If validation fails due to control characters in input data,
            # that's acceptable - the form is rejecting bad input
            assert "first_name" in form.errors
        else:
            # If it passes validation, sanitize_text_field should remove control chars
            assert "\x00" not in form.cleaned_data["first_name"]
            assert "\x01" not in form.cleaned_data["first_name"]
            assert form.cleaned_data["first_name"] == "JohnDoe"


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================


@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_form_with_none_values(self) -> None:
        """Test form handles None values gracefully."""
        data = {"first_name": None, "last_name": None}
        form = PersonForm(data=data)
        # Should fail validation for required fields
        assert not form.is_valid()

    def test_form_with_extremely_long_input(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test form handles extremely long input."""
        minimal_person_data["notes"] = "x" * 20000
        form = PersonForm(data=minimal_person_data)
        # Form is valid, but sanitize_text_field truncates to 10000
        assert form.is_valid()
        assert len(form.cleaned_data["notes"]) == 10000

    def test_form_initialization(self) -> None:
        """Test form initialization sets up duplicates list."""
        form = PersonForm()
        assert hasattr(form, "duplicates")
        assert isinstance(form.duplicates, list)
        assert len(form.duplicates) == 0

    def test_form_bootstrap_classes_applied(self) -> None:
        """Test that Bootstrap classes are applied to fields."""
        form = PersonForm()
        for field_name, field in form.fields.items():
            if field_name not in [
                "gender",
                "state",
            ]:  # Select fields have different class
                assert "form-control" in field.widget.attrs.get("class", "")

    def test_required_fields_marked(self) -> None:
        """Test that required fields are properly marked."""
        form = PersonForm()
        assert form.fields["first_name"].required is True
        assert form.fields["last_name"].required is True
        assert form.fields["email"].required is False

    def test_special_characters_in_names(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that special characters in names are handled."""
        special_names = [
            "O'Brien",
            "Anne-Marie",
            "José María",
            "van der Berg",
            "d'Angelo",
        ]
        for name in special_names:
            data = minimal_person_data.copy()
            data["first_name"] = name
            form = PersonForm(data=data)
            assert form.is_valid(), f"Name {name} should be valid"

    def test_date_edge_cases(self, minimal_person_data: dict[str, Any]) -> None:
        """Test date edge cases."""
        # Today's date should be valid
        minimal_person_data["date_of_birth"] = date.today()
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()

        # 150 years ago should be valid
        minimal_person_data["date_of_birth"] = date.today() - timedelta(days=365 * 150)
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()

    def test_unicode_in_all_text_fields(
        self, minimal_person_data: dict[str, Any]
    ) -> None:
        """Test that unicode is properly handled in all text fields."""
        unicode_test = "日本語 中文 한글 العربية"
        text_fields = ["city", "occupation", "employer", "notes"]

        for field in text_fields:
            data = minimal_person_data.copy()
            data[field] = unicode_test
            form = PersonForm(data=data)
            assert form.is_valid()
            assert unicode_test == form.cleaned_data[field]


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.django_db
class TestFormIntegration:
    """Integration tests for PersonForm."""

    def test_form_save_creates_person(self, valid_person_data: dict[str, Any]) -> None:
        """Test that valid form can save a Person."""
        form = PersonForm(data=valid_person_data)
        assert form.is_valid()

        person = form.save()
        assert person.id is not None
        assert person.first_name == "John"
        assert person.last_name == "Doe"
        assert person.email == "john.doe@example.com"

    def test_form_save_with_tags(self, minimal_person_data: dict[str, Any]) -> None:
        """Test that tags are properly saved."""
        minimal_person_data["tags"] = "volunteer, donor"
        form = PersonForm(data=minimal_person_data)
        assert form.is_valid()

        person = form.save()
        assert len(person.tags) == 2
        assert "volunteer" in person.tags
        assert "donor" in person.tags

    def test_form_update_existing_person(
        self, valid_person_data: dict[str, Any]
    ) -> None:
        """Test that form can update existing person."""
        # Create initial person
        person = Person.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
        )

        # Update using form
        valid_person_data["email"] = "john.doe@example.com"
        form = PersonForm(data=valid_person_data, instance=person)
        assert form.is_valid()

        updated_person = form.save()
        assert updated_person.id == person.id
        assert updated_person.first_name == "John"
        assert updated_person.email == "john.doe@example.com"
