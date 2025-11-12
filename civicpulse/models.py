import re
import uuid
from datetime import timedelta
from typing import Optional, cast

import phonenumbers
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.html import strip_tags
from phonenumbers import NumberParseException

# US State codes - moved to module level constant for better maintainability
VALID_US_STATE_CODES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",  # District of Columbia
]


def validate_phone_number(phone_number: str) -> None:
    """
    Validate phone number using the phonenumbers library.

    This provides more comprehensive validation than regex, including:
    - International format validation
    - Country-specific format validation
    - Number type validation (mobile, landline, etc.)

    Args:
        phone_number: The phone number string to validate

    Raises:
        ValidationError: If the phone number is invalid
    """
    if not phone_number.strip():
        return  # Allow empty phone numbers

    try:
        # Parse the number - default to US if no country code
        parsed_number = phonenumbers.parse(phone_number, "US")

        # Check if it's a possible number first (basic format check)
        if not phonenumbers.is_possible_number(parsed_number):
            raise ValidationError(f"'{phone_number}' is not a possible phone number.")

        # Check if the number is valid (more strict check)
        if not phonenumbers.is_valid_number(parsed_number):
            raise ValidationError(f"'{phone_number}' is not a valid phone number.")

    except NumberParseException as e:
        error_messages = {
            NumberParseException.INVALID_COUNTRY_CODE: "Invalid country code.",
            NumberParseException.NOT_A_NUMBER: "This is not a valid phone number.",
            NumberParseException.TOO_SHORT_NSN: "Phone number is too short.",
            NumberParseException.TOO_SHORT_AFTER_IDD: (
                "Phone number is too short after country code."
            ),
            NumberParseException.TOO_LONG: "Phone number is too long.",
        }
        message = error_messages.get(e.error_type, "Invalid phone number format.")
        raise ValidationError(f"'{phone_number}' - {message}") from e


def validate_voter_id(voter_id: str) -> None:
    """
    Validate voter ID format.

    Args:
        voter_id: The voter ID string to validate

    Raises:
        ValidationError: If the voter ID format is invalid
    """
    if not voter_id.strip():
        raise ValidationError("Voter ID is required.")

    # Basic length check - adjust based on your state's requirements
    if len(voter_id) < 3 or len(voter_id) > 50:
        raise ValidationError("Voter ID must be between 3 and 50 characters long.")

    # Check for valid characters (alphanumeric and basic symbols)
    if not re.match(r"^[A-Za-z0-9\-_]+$", voter_id):
        raise ValidationError(
            "Voter ID can only contain letters, numbers, hyphens, and underscores."
        )


def validate_zip_code(zip_code: str) -> None:
    """
    Validate US ZIP code format.

    Args:
        zip_code: The ZIP code string to validate

    Raises:
        ValidationError: If the ZIP code format is invalid
    """
    if not zip_code.strip():
        return  # Allow empty ZIP codes

    # Match 5-digit or 9-digit (ZIP+4) format
    if not re.match(r"^\d{5}(-\d{4})?$", zip_code):
        raise ValidationError(
            f"'{zip_code}' is not a valid US ZIP code format. "
            "Use XXXXX or XXXXX-XXXX format."
        )


def sanitize_text_field(value: str) -> str:
    """
    Sanitize text input to prevent XSS and other injection attacks.

    Args:
        value: The text value to sanitize

    Returns:
        Sanitized text with HTML tags removed and special chars escaped
    """
    if not value:
        return value

    # Remove script tags and their content completely
    value = re.sub(
        r"<script[^>]*>.*?</script>", "", value, flags=re.IGNORECASE | re.DOTALL
    )

    # Strip remaining HTML tags
    value = strip_tags(value)

    # Remove null bytes and other control characters
    value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", value)

    # Limit length to prevent DoS attacks
    if len(value) > 10000:  # Reasonable limit for text fields
        value = value[:10000]

    return value.strip()


def validate_text_content(value: str, field_name: str = "field") -> None:
    """
    Validate text content for security issues.

    Args:
        value: The text value to validate
        field_name: Name of the field for error messages

    Raises:
        ValidationError: If the text contains suspicious content
    """
    if not value:
        return

    # Check for suspicious patterns
    suspicious_patterns = [
        r"<script[^>]*>",  # Script tags
        r"javascript:",  # JavaScript URLs
        r"data:",  # Data URLs
        r"vbscript:",  # VBScript URLs
        r'on\w+\s*=\s*["\']?',  # Event handlers (more robust)
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValidationError(f"Suspicious content detected in {field_name}.")


class PersonManager(models.Manager):
    """Custom manager for Person model with optimized queries."""

    def get_queryset(self) -> QuerySet:
        """Return only active (non-soft-deleted) persons by default."""
        return super().get_queryset().filter(is_active=True)

    def all_with_deleted(self) -> QuerySet:
        """Return all persons including soft-deleted ones."""
        return super().get_queryset()

    def deleted_only(self) -> QuerySet:
        """Return only soft-deleted persons."""
        return super().get_queryset().filter(is_active=False)

    def with_voter_records(self) -> QuerySet:
        """Return persons with their voter records pre-fetched."""
        return self.select_related("voter_record")

    def with_recent_contacts(self, days: int = 30) -> QuerySet:
        """Return persons with recent contact attempts pre-fetched."""
        return self.prefetch_related("contact_attempts")

    def active_voters(self) -> QuerySet:
        """Return persons who are active voters."""
        return self.filter(voter_record__registration_status="active").select_related(
            "voter_record"
        )

    def by_location(
        self, state: str | None = None, zip_code: str | None = None
    ) -> QuerySet:
        """Filter persons by location."""
        queryset = self.all()
        if state:
            queryset = queryset.filter(state__iexact=state)
        if zip_code:
            queryset = queryset.filter(zip_code=zip_code)
        return queryset

    def search_by_name(self, search_term: str) -> QuerySet:
        """Search persons by name (first, last, or full name)."""
        if not search_term:
            return self.none()

        search_term = search_term.strip()
        return self.filter(
            Q(first_name__icontains=search_term)
            | Q(last_name__icontains=search_term)
            | Q(middle_name__icontains=search_term)
        ).distinct()

    def by_age_range(
        self, min_age: int | None = None, max_age: int | None = None
    ) -> QuerySet:
        """Filter persons by age range."""
        queryset = self.exclude(date_of_birth__isnull=True)
        today = timezone.now().date()

        if max_age is not None:
            min_birth_date = today.replace(year=today.year - max_age - 1)
            queryset = queryset.filter(date_of_birth__gt=min_birth_date)

        if min_age is not None:
            max_birth_date = today.replace(year=today.year - min_age)
            queryset = queryset.filter(date_of_birth__lte=max_birth_date)

        return queryset

    def without_voter_record(self) -> QuerySet:
        """Return persons who don't have voter records."""
        return self.filter(voter_record__isnull=True)

    def with_contact_in_period(self, days: int = 30) -> QuerySet:
        """Return persons contacted in the last N days."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(contact_attempts__contact_date__gte=cutoff_date).distinct()

    def advanced_search(
        self,
        search_query: str | None = None,
        state: str | None = None,
        zip_code: str | None = None,
        city: str | None = None,
        voter_status: str | None = None,
        party_affiliation: str | None = None,
        min_voter_score: int | None = None,
        max_voter_score: int | None = None,
        precinct: str | None = None,
        ward: str | None = None,
        congressional_district: str | None = None,
        state_house_district: str | None = None,
        state_senate_district: str | None = None,
        has_voter_record: bool | None = None,
        min_age: int | None = None,
        max_age: int | None = None,
        tags: list[str] | None = None,
    ) -> QuerySet:
        """
        Advanced search for persons with multiple filter criteria.

        Args:
            search_query: Text search across name, email, phone, and address fields
            state: Filter by state code
            zip_code: Filter by ZIP code
            city: Filter by city
            voter_status: Filter by voter registration status
            party_affiliation: Filter by party affiliation
            min_voter_score: Minimum voter score (0-100)
            max_voter_score: Maximum voter score (0-100)
            precinct: Filter by precinct
            ward: Filter by ward
            congressional_district: Filter by congressional district
            state_house_district: Filter by state house district
            state_senate_district: Filter by state senate district
            has_voter_record: Filter by presence of voter record
            min_age: Minimum age
            max_age: Maximum age
            tags: List of tags to filter by

        Returns:
            QuerySet of matching Person objects
        """
        queryset = self.select_related("voter_record")

        # Text search across multiple fields
        if search_query:
            search_query = search_query.strip()
            queryset = queryset.filter(
                Q(first_name__icontains=search_query)
                | Q(middle_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(phone_primary__icontains=search_query)
                | Q(phone_secondary__icontains=search_query)
                | Q(street_address__icontains=search_query)
                | Q(city__icontains=search_query)
                | Q(voter_record__voter_id__icontains=search_query)
            )

        # Location filters
        if state:
            queryset = queryset.filter(state__iexact=state)
        if zip_code:
            queryset = queryset.filter(zip_code=zip_code)
        if city:
            queryset = queryset.filter(city__icontains=city)

        # Voter record filters
        if voter_status:
            queryset = queryset.filter(voter_record__registration_status=voter_status)
        if party_affiliation:
            queryset = queryset.filter(
                voter_record__party_affiliation=party_affiliation
            )
        if min_voter_score is not None:
            queryset = queryset.filter(voter_record__voter_score__gte=min_voter_score)
        if max_voter_score is not None:
            queryset = queryset.filter(voter_record__voter_score__lte=max_voter_score)

        # Geographic/district filters
        if precinct:
            queryset = queryset.filter(voter_record__precinct=precinct)
        if ward:
            queryset = queryset.filter(voter_record__ward=ward)
        if congressional_district:
            queryset = queryset.filter(
                voter_record__congressional_district=congressional_district
            )
        if state_house_district:
            queryset = queryset.filter(
                voter_record__state_house_district=state_house_district
            )
        if state_senate_district:
            queryset = queryset.filter(
                voter_record__state_senate_district=state_senate_district
            )

        # Has voter record filter
        if has_voter_record is not None:
            if has_voter_record:
                queryset = queryset.filter(voter_record__isnull=False)
            else:
                queryset = queryset.filter(voter_record__isnull=True)

        # Age range filter
        if min_age is not None or max_age is not None:
            queryset = self.by_age_range(min_age, max_age)

        # Tags filter (JSON field - contains any of the specified tags)
        if tags:
            tag_filters = Q()
            for tag in tags:
                tag_filters |= Q(tags__contains=[tag])
            queryset = queryset.filter(tag_filters)

        return queryset.distinct()

    def search_full_text(self, search_query: str) -> QuerySet:
        """
        Full-text search across name and address fields.

        This is optimized for PostgreSQL full-text search capabilities,
        but falls back to case-insensitive contains for other databases.

        Args:
            search_query: The search query string

        Returns:
            QuerySet of matching Person objects
        """
        if not search_query:
            return self.none()

        search_query = search_query.strip()

        # For PostgreSQL, we can use full-text search vectors
        # For now, we'll use icontains which works across all databases
        # TODO: Implement PostgreSQL-specific full-text search when migrating
        # to Postgres
        return self.filter(
            Q(first_name__icontains=search_query)
            | Q(middle_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(street_address__icontains=search_query)
            | Q(city__icontains=search_query)
            | Q(email__icontains=search_query)
        ).distinct()

    def by_voter_status(self, status: str) -> QuerySet:
        """Filter by voter registration status."""
        return self.filter(voter_record__registration_status=status).select_related(
            "voter_record"
        )

    def by_party(self, party: str) -> QuerySet:
        """Filter by party affiliation."""
        return self.filter(voter_record__party_affiliation=party).select_related(
            "voter_record"
        )

    def by_voter_score_range(
        self, min_score: int | None = None, max_score: int | None = None
    ) -> QuerySet:
        """Filter by voter score range."""
        queryset = self.filter(voter_record__isnull=False).select_related(
            "voter_record"
        )
        if min_score is not None:
            queryset = queryset.filter(voter_record__voter_score__gte=min_score)
        if max_score is not None:
            queryset = queryset.filter(voter_record__voter_score__lte=max_score)
        return queryset

    def by_district(
        self,
        congressional: str | None = None,
        state_house: str | None = None,
        state_senate: str | None = None,
        precinct: str | None = None,
        ward: str | None = None,
    ) -> QuerySet:
        """Filter by geographic/voting districts."""
        queryset = self.filter(voter_record__isnull=False).select_related(
            "voter_record"
        )
        if congressional:
            queryset = queryset.filter(
                voter_record__congressional_district=congressional
            )
        if state_house:
            queryset = queryset.filter(voter_record__state_house_district=state_house)
        if state_senate:
            queryset = queryset.filter(voter_record__state_senate_district=state_senate)
        if precinct:
            queryset = queryset.filter(voter_record__precinct=precinct)
        if ward:
            queryset = queryset.filter(voter_record__ward=ward)
        return queryset

    def high_priority_voters(self, min_score: int = 70) -> QuerySet:
        """Return high-priority voters based on voter score."""
        return self.filter(
            voter_record__isnull=False, voter_record__voter_score__gte=min_score
        ).select_related("voter_record")

    def by_tags(self, tags: list[str], match_all: bool = False) -> QuerySet:
        """
        Filter by tags.

        Args:
            tags: List of tags to filter by
            match_all: If True, person must have all tags. If False, any tag matches.

        Returns:
            QuerySet of matching Person objects
        """
        if not tags:
            return self.all()

        if match_all:
            # Person must have all specified tags
            queryset = self.all()
            for tag in tags:
                queryset = queryset.filter(tags__contains=[tag])
            return queryset
        else:
            # Person must have at least one of the specified tags
            tag_filters = Q()
            for tag in tags:
                tag_filters |= Q(tags__contains=[tag])
            return self.filter(tag_filters).distinct()

    def in_district(self, district_id: str) -> QuerySet:
        """Return persons in a specific district."""
        return self.filter(person_districts__district__id=district_id).distinct()

    def in_districts(self, district_ids: list[str]) -> QuerySet:
        """Return persons in any of the specified districts."""
        return self.filter(person_districts__district__id__in=district_ids).distinct()

    def by_district_type(self, district_type: str) -> QuerySet:
        """Return persons by district type (e.g., federal_senate, state_house)."""
        return self.filter(
            person_districts__district__district_type=district_type
        ).distinct()

    def with_districts(self) -> QuerySet:
        """Return persons with their districts and officeholders prefetched."""
        return self.prefetch_related(
            "person_districts__district",
            "person_districts__district__officeholders",
        )

    def in_district_with_officeholder(self, district_id: str) -> QuerySet:
        """
        Return persons in a specific district with current officeholder information.

        Args:
            district_id: The UUID of the district

        Returns:
            QuerySet of Person objects in the district with officeholder data
        """
        return (
            self.filter(person_districts__district__id=district_id)
            .select_related("voter_record")
            .prefetch_related(
                "person_districts__district",
                "person_districts__district__officeholders",
            )
            .distinct()
        )

    def by_assignment_method(self, method: str) -> QuerySet:
        """
        Filter persons by how they were assigned to districts.

        Args:
            method: Assignment method
                (manual, voter_record, geocoding, zip_match, import)

        Returns:
            QuerySet of Person objects assigned by the specified method
        """
        return self.filter(person_districts__assignment_method=method).distinct()

    def high_confidence_assignments(self, min_confidence: float = 90.0) -> QuerySet:
        """
        Return persons with high-confidence district assignments.

        Args:
            min_confidence: Minimum confidence score (0-100, default 90.0)

        Returns:
            QuerySet of Person objects with confidence >= min_confidence
        """
        return (
            self.filter(person_districts__confidence__gte=min_confidence)
            .prefetch_related("person_districts__district")
            .distinct()
        )

    def without_district_assignment(self) -> QuerySet:
        """Return persons who have not been assigned to any district."""
        return self.filter(person_districts__isnull=True)

    def voters_in_districts(self, district_ids: list[str]) -> QuerySet:
        """
        Return active voters in specified districts.

        Args:
            district_ids: List of district UUIDs

        Returns:
            QuerySet of Person objects who are active voters in the districts
        """
        return (
            self.filter(
                person_districts__district__id__in=district_ids,
                voter_record__registration_status="active",
            )
            .select_related("voter_record")
            .prefetch_related("person_districts__district")
            .distinct()
        )


class VoterRecordManager(models.Manager):
    """Custom manager for VoterRecord model with optimized queries."""

    def with_person_details(self) -> QuerySet:
        """Return voter records with person details pre-fetched."""
        return self.select_related("person")

    def active_voters(self) -> QuerySet:
        """Return only active voter registrations."""
        return self.filter(registration_status="active").select_related("person")

    def by_party(self, party: str) -> QuerySet:
        """Filter by party affiliation."""
        return self.filter(party_affiliation=party).select_related("person")

    def high_frequency_voters(self, min_score: int = 70) -> QuerySet:
        """Return voters with high voting frequency."""
        return self.filter(voter_score__gte=min_score).select_related("person")


class ContactAttemptManager(models.Manager):
    """Custom manager for ContactAttempt model with optimized queries."""

    def with_related(self) -> QuerySet:
        """Return contact attempts with person and contacted_by pre-fetched."""
        return self.select_related("person", "contacted_by")

    def successful_contacts(self) -> QuerySet:
        """Return only successful contact attempts."""
        return self.filter(
            result__in=["contacted", "left_message", "callback"]
        ).select_related("person", "contacted_by")

    def requiring_followup(self) -> QuerySet:
        """Return contacts that require follow-up."""
        return self.filter(
            follow_up_required=True, follow_up_date__gte=timezone.now().date()
        ).select_related("person", "contacted_by")

    def by_campaign(self, campaign: str) -> QuerySet:
        """Filter by campaign."""
        return self.filter(campaign=campaign).select_related("person", "contacted_by")

    def positive_sentiment(self) -> QuerySet:
        """Return contacts with positive sentiment."""
        return self.filter(sentiment__in=["strong_support", "support"]).select_related(
            "person", "contacted_by"
        )


class User(AbstractUser):
    """Extended User model with additional fields for roles and permissions."""

    ROLE_CHOICES = [
        ("admin", "Administrator"),
        ("organizer", "Organizer"),
        ("volunteer", "Volunteer"),
        ("viewer", "Viewer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer")
    organization = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        validators=[validate_phone_number],
    )
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["role"]),
            models.Index(fields=["organization"]),
        ]

    def clean(self) -> None:
        """Validate the User instance."""
        super().clean()

        # Validate organization is required for certain roles
        if self.role in ["admin", "organizer"] and not self.organization.strip():
            raise ValidationError(
                {
                    "organization": (
                        "Organization is required for admin and organizer roles."
                    )
                }
            )

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"

    def get_formatted_phone_number(self, format_type: str = "national") -> str:
        """
        Get formatted phone number.

        Args:
            format_type: 'national', 'international', or 'e164'

        Returns:
            Formatted phone number or original string if parsing fails
        """
        if not self.phone_number.strip():
            return self.phone_number

        try:
            parsed_number = phonenumbers.parse(self.phone_number, "US")
            if phonenumbers.is_valid_number(parsed_number):
                format_map = {
                    "national": phonenumbers.PhoneNumberFormat.NATIONAL,
                    "international": phonenumbers.PhoneNumberFormat.INTERNATIONAL,
                    "e164": phonenumbers.PhoneNumberFormat.E164,
                }
                phone_format = format_map.get(
                    format_type, phonenumbers.PhoneNumberFormat.NATIONAL
                )
                return phonenumbers.format_number(parsed_number, phone_format)
        except NumberParseException:
            pass

        return self.phone_number  # Return original if parsing fails


class PasswordHistory(models.Model):
    """Track password history to prevent reuse of recent passwords."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_history",
    )
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_history"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Password history for {self.user.username} at {self.created_at}"


class Person(models.Model):
    """Model representing a person/voter with all their information."""

    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other"),
        ("U", "Unknown"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Basic Information
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    suffix = models.CharField(max_length=10, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default="U")

    # Contact Information
    email = models.EmailField(blank=True, db_index=True)
    phone_primary = models.CharField(
        max_length=20,
        blank=True,
        validators=[validate_phone_number],
    )
    phone_secondary = models.CharField(
        max_length=20,
        blank=True,
        validators=[validate_phone_number],
    )

    # Address Information
    street_address = models.CharField(max_length=255, blank=True)
    apartment_number = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zip_code = models.CharField(
        max_length=10, blank=True, validators=[validate_zip_code]
    )
    county = models.CharField(max_length=100, blank=True)

    # Additional Information
    occupation = models.CharField(max_length=100, blank=True)
    employer = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)

    # Metadata
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="persons_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft delete functionality
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="persons_deleted",
        blank=True,
    )

    # Custom manager
    objects = PersonManager()

    class Meta:
        db_table = "persons"
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["email"]),
            models.Index(fields=["phone_primary"]),
            models.Index(fields=["phone_secondary"]),
            models.Index(fields=["zip_code"]),
            models.Index(fields=["state", "zip_code"]),
            models.Index(fields=["date_of_birth"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["created_by"]),
            # Composite index for duplicate detection
            models.Index(fields=["first_name", "last_name", "date_of_birth"]),
        ]
        unique_together = [["first_name", "last_name", "date_of_birth"]]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def clean(self) -> None:
        """Validate the Person instance."""
        super().clean()

        # Sanitize text fields first, then validate
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

        for field_name in text_fields:
            value = getattr(self, field_name, "")
            if value:
                # Sanitize the content first
                sanitized_value = sanitize_text_field(value)
                setattr(self, field_name, sanitized_value)
                # Then validate for any remaining security issues
                validate_text_content(sanitized_value, field_name)

        # Validate ZIP code format if provided
        if self.zip_code:
            validate_zip_code(self.zip_code)

        # Validate date of birth is not in the future
        if self.date_of_birth and self.date_of_birth > timezone.now().date():
            raise ValidationError(
                {"date_of_birth": "Date of birth cannot be in the future."}
            )

        # Validate age is reasonable (not older than 150 years)
        if self.date_of_birth:
            today = timezone.now().date()
            age = today.year - self.date_of_birth.year
            if age > 150:
                raise ValidationError(
                    {"date_of_birth": "Date of birth indicates an unrealistic age."}
                )

        # Validate state is a valid US state code if provided
        if self.state:
            if self.state.upper() not in VALID_US_STATE_CODES:
                raise ValidationError(
                    {"state": f"'{self.state}' is not a valid US state code."}
                )

        # Validate email domain if provided
        if self.email and "@" in self.email:
            domain = self.email.split("@")[-1].lower()
            # Check for suspicious domains - configurable via settings
            suspicious_domains = getattr(
                settings,
                "SUSPICIOUS_EMAIL_DOMAINS",
                ["example.com", "test.com", "localhost"],
            )
            if domain in suspicious_domains:
                raise ValidationError(
                    {"email": f"Email domain '{domain}' is not allowed."}
                )

    @property
    def full_name(self) -> str:
        """Return the full name including middle name and suffix if present."""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        if self.suffix:
            parts.append(self.suffix)
        return " ".join(parts)

    @property
    def age(self) -> int | None:
        """Calculate age based on date of birth."""
        if not self.date_of_birth:
            return None
        today = timezone.now().date()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    def get_formatted_phone_primary(self, format_type: str = "national") -> str:
        """
        Get formatted primary phone number.

        Args:
            format_type: 'national', 'international', or 'e164'

        Returns:
            Formatted phone number or original string if parsing fails
        """
        return self._format_phone_number(self.phone_primary, format_type)

    def get_formatted_phone_secondary(self, format_type: str = "national") -> str:
        """
        Get formatted secondary phone number.

        Args:
            format_type: 'national', 'international', or 'e164'

        Returns:
            Formatted phone number or original string if parsing fails
        """
        return self._format_phone_number(self.phone_secondary, format_type)

    def get_potential_duplicates(self) -> QuerySet:
        """
        Find potential duplicate persons based on name and contact info.

        Returns:
            QuerySet of Person objects that might be duplicates
        """
        filters = Q()

        # Same name and DOB
        if self.date_of_birth:
            filters |= Q(
                first_name__iexact=self.first_name,
                last_name__iexact=self.last_name,
                date_of_birth=self.date_of_birth,
            )

        # Same email (if provided)
        if self.email.strip():
            filters |= Q(email__iexact=self.email)

        # Same primary phone (if provided)
        if self.phone_primary.strip():
            filters |= Q(phone_primary=self.phone_primary)

        # Same secondary phone (if provided)
        if self.phone_secondary.strip():
            filters |= Q(phone_secondary=self.phone_secondary)

        # Same name and address
        if self.street_address.strip() and self.zip_code.strip():
            filters |= Q(
                first_name__iexact=self.first_name,
                last_name__iexact=self.last_name,
                street_address__iexact=self.street_address,
                zip_code=self.zip_code,
            )

        queryset = Person.objects.filter(filters)

        # Exclude self if this is an existing person
        if self.pk:
            queryset = queryset.exclude(pk=self.pk)

        return queryset.distinct()

    def soft_delete(self, user: Optional["User"] = None) -> None:
        """
        Soft delete this person.

        Args:
            user: The user performing the deletion
        """
        self.is_active = False
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=["is_active", "deleted_at", "deleted_by"])

    def restore(self) -> None:
        """Restore a soft-deleted person."""
        self.is_active = True
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_active", "deleted_at", "deleted_by"])

    def _format_phone_number(
        self, phone_number: str, format_type: str = "national"
    ) -> str:
        """
        Format a phone number using phonenumbers library.

        Args:
            phone_number: The phone number to format
            format_type: 'national', 'international', or 'e164'

        Returns:
            Formatted phone number or original string if parsing fails
        """
        if not phone_number.strip():
            return phone_number

        try:
            parsed_number = phonenumbers.parse(phone_number, "US")
            if phonenumbers.is_valid_number(parsed_number):
                format_map = {
                    "national": phonenumbers.PhoneNumberFormat.NATIONAL,
                    "international": phonenumbers.PhoneNumberFormat.INTERNATIONAL,
                    "e164": phonenumbers.PhoneNumberFormat.E164,
                }
                phone_format = format_map.get(
                    format_type, phonenumbers.PhoneNumberFormat.NATIONAL
                )
                return phonenumbers.format_number(parsed_number, phone_format)
        except NumberParseException:
            pass

        return phone_number  # Return original if parsing fails


class VoterRecord(models.Model):
    """Model for voter registration and voting history information."""

    REGISTRATION_STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("pending", "Pending"),
        ("cancelled", "Cancelled"),
        ("suspended", "Suspended"),
    ]

    PARTY_AFFILIATION_CHOICES = [
        ("DEM", "Democratic"),
        ("REP", "Republican"),
        ("IND", "Independent"),
        ("GRN", "Green"),
        ("LIB", "Libertarian"),
        ("OTH", "Other"),
        ("NON", "No Party Affiliation"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.OneToOneField(
        Person, on_delete=models.CASCADE, related_name="voter_record"
    )

    # Registration Information
    voter_id = models.CharField(
        max_length=50, unique=True, db_index=True, validators=[validate_voter_id]
    )
    registration_date = models.DateField(null=True, blank=True)
    registration_status = models.CharField(
        max_length=20, choices=REGISTRATION_STATUS_CHOICES, default="active"
    )
    party_affiliation = models.CharField(
        max_length=3, choices=PARTY_AFFILIATION_CHOICES, default="NON"
    )

    # Voting Location
    precinct = models.CharField(max_length=50, blank=True)
    ward = models.CharField(max_length=50, blank=True)
    congressional_district = models.CharField(max_length=10, blank=True)
    state_house_district = models.CharField(max_length=10, blank=True)
    state_senate_district = models.CharField(max_length=10, blank=True)
    polling_location = models.CharField(max_length=255, blank=True)

    # Voting History (stored as JSON for flexibility)
    voting_history = models.JSONField(default=list, blank=True)

    # Absentee/Mail Voting
    absentee_voter = models.BooleanField(default=False)
    mail_ballot_requested = models.BooleanField(default=False)
    mail_ballot_sent_date = models.DateField(null=True, blank=True)
    mail_ballot_returned_date = models.DateField(null=True, blank=True)

    # Metadata
    last_voted_date = models.DateField(null=True, blank=True)
    voter_score = models.IntegerField(default=0)  # Frequency of voting (0-100)
    source = models.CharField(max_length=100, blank=True)  # Data source
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Custom manager
    objects = VoterRecordManager()

    class Meta:
        db_table = "voter_records"
        indexes = [
            models.Index(fields=["voter_id"]),
            models.Index(fields=["registration_status"]),
            models.Index(fields=["party_affiliation"]),
            models.Index(fields=["precinct"]),
            models.Index(fields=["ward"]),
            models.Index(fields=["last_voted_date"]),
            models.Index(fields=["voter_score"]),
            models.Index(fields=["registration_date"]),
            models.Index(fields=["congressional_district"]),
            models.Index(fields=["state_house_district"]),
            models.Index(fields=["state_senate_district"]),
            # Composite indexes for common queries
            models.Index(fields=["registration_status", "party_affiliation"]),
            models.Index(fields=["precinct", "ward"]),
            models.Index(fields=["voter_score", "last_voted_date"]),
        ]

    def __str__(self) -> str:
        return f"Voter {self.voter_id} - {self.person.full_name}"

    def clean(self) -> None:
        """Validate the VoterRecord instance."""
        super().clean()

        # Validate voter ID format
        validate_voter_id(self.voter_id)

        # Validate registration date is not in the future
        if self.registration_date and self.registration_date > timezone.now().date():
            raise ValidationError(
                {"registration_date": "Registration date cannot be in the future."}
            )

        # Validate last voted date is not in the future
        if self.last_voted_date and self.last_voted_date > timezone.now().date():
            raise ValidationError(
                {"last_voted_date": "Last voted date cannot be in the future."}
            )

        # Validate voter score is within reasonable range
        if not (0 <= self.voter_score <= 100):
            raise ValidationError(
                {"voter_score": "Voter score must be between 0 and 100."}
            )

        # Validate mail ballot dates are logical
        if (
            self.mail_ballot_sent_date
            and self.mail_ballot_returned_date
            and self.mail_ballot_sent_date > self.mail_ballot_returned_date
        ):
            raise ValidationError(
                {"mail_ballot_returned_date": "Return date cannot be before sent date."}
            )

    @property
    def voting_frequency(self) -> str:
        """Return a human-readable voting frequency based on voter score."""
        if self.voter_score >= 80:
            return "Very High"
        elif self.voter_score >= 60:
            return "High"
        elif self.voter_score >= 40:
            return "Medium"
        elif self.voter_score >= 20:
            return "Low"
        else:
            return "Very Low"


class ContactAttempt(models.Model):
    """Model for tracking outreach and contact attempts."""

    CONTACT_TYPE_CHOICES = [
        ("phone", "Phone Call"),
        ("text", "Text Message"),
        ("email", "Email"),
        ("door", "Door Knock"),
        ("mail", "Postal Mail"),
        ("social", "Social Media"),
        ("event", "Event"),
        ("other", "Other"),
    ]

    RESULT_CHOICES = [
        ("contacted", "Successfully Contacted"),
        ("no_answer", "No Answer"),
        ("left_message", "Left Message"),
        ("wrong_number", "Wrong Number"),
        ("refused", "Refused"),
        ("callback", "Callback Requested"),
        ("not_home", "Not Home"),
        ("moved", "Moved"),
        ("deceased", "Deceased"),
        ("other", "Other"),
    ]

    SENTIMENT_CHOICES = [
        ("strong_support", "Strong Support"),
        ("support", "Support"),
        ("neutral", "Neutral"),
        ("oppose", "Oppose"),
        ("strong_oppose", "Strong Oppose"),
        ("undecided", "Undecided"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="contact_attempts"
    )

    # Contact Information
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPE_CHOICES)
    contact_date = models.DateTimeField()
    contacted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="contacts_made"
    )

    # Result Information
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    sentiment = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, blank=True)

    # Conversation Details
    issues_discussed = models.JSONField(default=list, blank=True)
    commitments = models.JSONField(default=list, blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)

    # Notes and Details
    notes = models.TextField(blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)

    # Campaign/Event Association
    campaign = models.ForeignKey(
        "Campaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_attempts",
    )
    event = models.CharField(max_length=100, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Custom manager
    objects = ContactAttemptManager()

    class Meta:
        db_table = "contact_attempts"
        indexes = [
            models.Index(fields=["contact_date"]),
            models.Index(fields=["contact_type"]),
            models.Index(fields=["result"]),
            models.Index(fields=["sentiment"]),
            models.Index(fields=["follow_up_required", "follow_up_date"]),
            models.Index(fields=["campaign"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-contact_date"]

    def __str__(self) -> str:
        date_str = self.contact_date.strftime("%Y-%m-%d")
        return f"{self.contact_type} - {self.person.full_name} on {date_str}"

    def clean(self) -> None:
        """Validate the ContactAttempt instance."""
        super().clean()

        # Sanitize text fields first, then validate
        text_fields = ["notes", "event"]
        for field_name in text_fields:
            value = getattr(self, field_name, "")
            if value:
                # Sanitize the content first
                sanitized_value = sanitize_text_field(value)
                setattr(self, field_name, sanitized_value)
                # Then validate for any remaining security issues
                validate_text_content(sanitized_value, field_name)

        # Validate contact date is not in the future
        if self.contact_date and self.contact_date > timezone.now():
            raise ValidationError(
                {"contact_date": "Contact date cannot be in the future."}
            )

        # Validate contact date is not too far in the past (e.g., 10 years)
        if self.contact_date:
            ten_years_ago = timezone.now() - timedelta(days=3650)
            if self.contact_date < ten_years_ago:
                raise ValidationError(
                    {
                        "contact_date": (
                            "Contact date seems unreasonably old (over 10 years)."
                        )
                    }
                )

        # Validate follow-up date is not in the past if follow-up is required
        if (
            self.follow_up_required
            and self.follow_up_date
            and self.follow_up_date < timezone.now().date()
        ):
            raise ValidationError(
                {
                    "follow_up_date": (
                        "Follow-up date cannot be in the past when follow-up is "
                        "required."
                    )
                }
            )

        # Validate duration is reasonable
        if self.duration_minutes is not None and self.duration_minutes < 0:
            raise ValidationError({"duration_minutes": "Duration cannot be negative."})

        if self.duration_minutes is not None and self.duration_minutes > 480:
            raise ValidationError(
                {"duration_minutes": "Duration seems unreasonably long (over 8 hours)."}
            )

        # Validate JSON fields for security
        if self.issues_discussed:
            for issue in self.issues_discussed:
                if isinstance(issue, str):
                    validate_text_content(issue, "issues_discussed")

        if self.commitments:
            for commitment in self.commitments:
                if isinstance(commitment, str):
                    validate_text_content(commitment, "commitments")

    @property
    def was_successful(self) -> bool:
        """Return True if the contact attempt was successful."""
        return self.result in ["contacted", "left_message", "callback"]

    @property
    def is_positive_sentiment(self) -> bool:
        """Return True if the sentiment is positive."""
        return self.sentiment in ["strong_support", "support"]


class CampaignManager(models.Manager):
    """Custom manager for Campaign model with soft delete support."""

    def get_queryset(self) -> QuerySet:
        """Return only active (non-soft-deleted) campaigns by default."""
        return super().get_queryset().filter(is_active=True)

    def all_with_deleted(self) -> QuerySet:
        """Return all campaigns including soft-deleted ones."""
        return super().get_queryset()

    def active(self) -> QuerySet:
        """Return only active campaigns."""
        return self.filter(status="active")

    def by_status(self, status: str) -> QuerySet:
        """Filter campaigns by status."""
        return self.filter(status=status)

    def upcoming_elections(self) -> QuerySet:
        """Return campaigns with upcoming elections."""
        return self.filter(election_date__gte=timezone.now().date()).order_by(
            "election_date"
        )

    def past_elections(self) -> QuerySet:
        """Return campaigns with past elections."""
        return self.filter(election_date__lt=timezone.now().date()).order_by(
            "-election_date"
        )

    def search_by_name(self, search_term: str) -> QuerySet:
        """Search campaigns by name or candidate name."""
        if not search_term:
            return self.none()

        search_term = search_term.strip()
        return self.filter(
            Q(name__icontains=search_term) | Q(candidate_name__icontains=search_term)
        ).distinct()

    def by_organization(self, organization: str) -> QuerySet:
        """Filter campaigns by organization."""
        return self.filter(organization=organization)

    def by_scope(self, scope: str) -> QuerySet:
        """Filter campaigns by geographical scope."""
        return self.filter(scope=scope)

    def targeting_district(self, district_id: str) -> QuerySet:
        """Return campaigns targeting a specific district."""
        return self.filter(target_districts__id=district_id).distinct()

    def targeting_districts(self, district_ids: list[str]) -> QuerySet:
        """Return campaigns targeting any of the specified districts."""
        return self.filter(target_districts__id__in=district_ids).distinct()

    def multi_district(self) -> QuerySet:
        """Return campaigns targeting multiple districts."""
        return self.filter(scope="multi_district").prefetch_related("target_districts")

    def single_district(self) -> QuerySet:
        """Return campaigns targeting a single district."""
        return self.filter(scope="district").prefetch_related("target_districts")

    def statewide(self) -> QuerySet:
        """Return statewide campaigns."""
        return self.filter(scope="statewide")

    def national(self) -> QuerySet:
        """Return national campaigns."""
        return self.filter(scope="national")

    def with_districts(self) -> QuerySet:
        """Return campaigns with their target districts prefetched."""
        return self.prefetch_related(
            "target_districts", "target_districts__officeholders"
        )

    def eligible_voters_for_campaign(self, campaign_id: str) -> QuerySet:
        """
        Return persons eligible for contact based on campaign's target districts.

        Args:
            campaign_id: The UUID of the campaign

        Returns:
            QuerySet of Person objects who are in the campaign's target districts
        """
        try:
            campaign = cast("Campaign", self.get(id=campaign_id))
        except Campaign.DoesNotExist:
            return Person.objects.none()

        # If campaign has target districts, filter by those
        if campaign.target_districts.exists():
            district_ids = campaign.target_districts.values_list("id", flat=True)
            return (
                Person.objects.filter(person_districts__district__id__in=district_ids)
                .select_related("voter_record")
                .prefetch_related("person_districts__district")
                .distinct()
            )

        # If no target districts specified, return all persons
        # (this could be filtered further based on campaign scope in the future)
        return Person.objects.select_related("voter_record").all()

    def contacts_in_districts(
        self, campaign_id: str, district_ids: list[str] | None = None
    ) -> QuerySet:
        """
        Return persons who are contacts for a campaign in specific districts.

        Args:
            campaign_id: The UUID of the campaign
            district_ids: Optional list of district UUIDs to filter by

        Returns:
            QuerySet of Person objects who are in the specified districts
        """
        try:
            campaign = cast("Campaign", self.get(id=campaign_id))
        except Campaign.DoesNotExist:
            return Person.objects.none()

        # Start with persons in the campaign's target districts
        base_queryset = Person.objects.filter(
            person_districts__district__in=campaign.target_districts.all()
        )

        # Further filter by specific districts if provided
        if district_ids:
            base_queryset = base_queryset.filter(
                person_districts__district__id__in=district_ids
            )

        return (
            base_queryset.select_related("voter_record")
            .prefetch_related("person_districts__district")
            .distinct()
        )


class Campaign(models.Model):
    """Model representing a political campaign."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    ]

    SCOPE_CHOICES = [
        ("district", "Single District"),
        ("multi_district", "Multiple Districts"),
        ("statewide", "Statewide"),
        ("national", "National"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Campaign Information
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    candidate_name = models.CharField(max_length=200)
    election_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    organization = models.CharField(max_length=255, blank=True)

    # District Targeting
    target_districts: models.ManyToManyField = models.ManyToManyField(
        "District",
        related_name="campaigns",
        blank=True,
        help_text="Districts this campaign targets for contact outreach",
    )
    scope = models.CharField(
        max_length=50,
        choices=SCOPE_CHOICES,
        default="district",
        help_text="Geographical scope of the campaign",
    )

    # Audit fields
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="campaigns_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft delete functionality
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="campaigns_deleted",
        blank=True,
    )

    # Custom manager
    objects = CampaignManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Campaign"
        verbose_name_plural = "Campaigns"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["election_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["organization"]),
            models.Index(fields=["candidate_name"]),
            models.Index(fields=["scope"]),
            # Composite index for common queries
            models.Index(fields=["status", "election_date"]),
            models.Index(fields=["scope", "status"]),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        """Validate the Campaign instance."""
        super().clean()

        # Sanitize text fields first, then validate
        text_fields = ["name", "description", "candidate_name"]
        for field_name in text_fields:
            value = getattr(self, field_name, "")
            if value:
                # Sanitize the content first
                sanitized_value = sanitize_text_field(value)
                setattr(self, field_name, sanitized_value)
                # Then validate for any remaining security issues
                validate_text_content(sanitized_value, field_name)

        # Validate election date is not in the past (for new campaigns)
        if self.election_date and not self.pk:  # Only for new campaigns
            if self.election_date < timezone.now().date():
                raise ValidationError(
                    {"election_date": "Election date cannot be in the past."}
                )

        # Validate election date is not too far in the future (e.g., 10 years)
        if self.election_date:
            ten_years_from_now = timezone.now().date() + timedelta(days=3650)
            if self.election_date > ten_years_from_now:
                raise ValidationError(
                    {
                        "election_date": (
                            "Election date seems unreasonably far in the future "
                            "(over 10 years)."
                        )
                    }
                )

        # Note: Campaign name uniqueness is handled by the form-level duplicate
        # detection workflow (CampaignForm.clean()) to allow for user confirmation.
        # Model-level validation would prevent the duplicate detection and confirmation
        # workflow from functioning properly.

        # Validate status is a valid choice
        valid_statuses = [choice[0] for choice in self.STATUS_CHOICES]
        if self.status and self.status not in valid_statuses:
            raise ValidationError(
                {
                    "status": (
                        f"'{self.status}' is not a valid status. "
                        f"Choose from: {', '.join(valid_statuses)}."
                    )
                }
            )

    def soft_delete(self, user: Optional["User"] = None) -> None:
        """
        Soft delete this campaign.

        Args:
            user: The user performing the deletion
        """
        self.is_active = False
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=["is_active", "deleted_at", "deleted_by"])

    def restore(self) -> None:
        """Restore a soft-deleted campaign."""
        self.is_active = True
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_active", "deleted_at", "deleted_by"])

    @property
    def is_upcoming(self) -> bool:
        """Return True if the election date is in the future."""
        return self.election_date >= timezone.now().date()

    @property
    def days_until_election(self) -> int | None:
        """Calculate days until election."""
        if not self.election_date:
            return None
        today = timezone.now().date()
        if self.election_date < today:
            return None  # Election has passed
        return (self.election_date - today).days


class District(models.Model):
    """Model representing electoral districts."""

    DISTRICT_TYPE_CHOICES = [
        ("federal_senate", "Federal Senate"),
        ("federal_house", "Federal House"),
        ("state_senate", "State Senate"),
        ("state_house", "State House"),
        ("county", "County"),
        ("school_board", "School Board"),
        ("municipality", "Municipality"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # District Information
    name = models.CharField(max_length=200)
    district_code = models.CharField(max_length=50, unique=True, db_index=True)
    district_type = models.CharField(max_length=20, choices=DISTRICT_TYPE_CHOICES)
    state = models.CharField(max_length=2)

    # Geographic Information
    boundary_description = models.TextField(blank=True)
    counties_covered = models.JSONField(default=list, blank=True)
    zip_codes_covered = models.JSONField(default=list, blank=True)

    # Administrative Information
    election_authority = models.CharField(max_length=255, blank=True)
    population = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "districts"
        verbose_name_plural = "Districts"
        ordering = ["state", "district_type", "name"]
        indexes = [
            models.Index(fields=["district_code"]),
            models.Index(fields=["district_type"]),
            models.Index(fields=["state"]),
            models.Index(fields=["state", "district_type"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.district_code})"

    def clean(self) -> None:
        """Validate the District instance."""
        super().clean()

        # Sanitize text fields
        text_fields = ["name", "boundary_description", "election_authority", "notes"]
        for field_name in text_fields:
            value = getattr(self, field_name, "")
            if value:
                sanitized_value = sanitize_text_field(value)
                setattr(self, field_name, sanitized_value)
                validate_text_content(sanitized_value, field_name)

        # Validate state is a valid US state code
        if self.state:
            if self.state.upper() not in VALID_US_STATE_CODES:
                raise ValidationError(
                    {"state": f"'{self.state}' is not a valid US state code."}
                )

        # Validate district_code format
        if self.district_code:
            if not re.match(r"^[A-Z]{2}-\d+$", self.district_code):
                raise ValidationError(
                    {
                        "district_code": (
                            "District code must be in format 'XX-NN' "
                            "(e.g., 'PA-05', 'CA-12')."
                        )
                    }
                )

        # Validate population is reasonable if provided
        if self.population is not None and self.population < 0:
            raise ValidationError({"population": "Population cannot be negative."})

        if self.population is not None and self.population > 50_000_000:
            raise ValidationError(
                {"population": "Population seems unreasonably large."}
            )


class Officeholder(models.Model):
    """Model representing elected officials."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship to District
    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name="officeholders"
    )

    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    party_affiliation = models.CharField(max_length=50, blank=True)

    # Term Information
    term_start = models.DateField()
    term_end = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=True, db_index=True)

    # Contact Information
    office_phone = models.CharField(
        max_length=20, blank=True, validators=[validate_phone_number]
    )
    office_email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    office_address = models.TextField(blank=True)

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "officeholders"
        ordering = ["-is_current", "-term_start"]
        indexes = [
            models.Index(fields=["is_current"]),
            models.Index(fields=["district"]),
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["term_start"]),
            models.Index(fields=["term_end"]),
            models.Index(fields=["district", "is_current"]),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} - {self.district.district_code}"

    @property
    def full_name(self) -> str:
        """Return the full name of the officeholder."""
        return f"{self.first_name} {self.last_name}"

    def clean(self) -> None:
        """Validate the Officeholder instance."""
        super().clean()

        # Sanitize text fields
        text_fields = ["first_name", "last_name", "party_affiliation", "office_address"]
        for field_name in text_fields:
            value = getattr(self, field_name, "")
            if value:
                sanitized_value = sanitize_text_field(value)
                setattr(self, field_name, sanitized_value)
                validate_text_content(sanitized_value, field_name)

        # Validate term dates
        if self.term_start and self.term_start > timezone.now().date():
            raise ValidationError(
                {"term_start": "Term start date cannot be in the future."}
            )

        if self.term_end:
            if self.term_end < self.term_start:
                raise ValidationError(
                    {"term_end": "Term end date cannot be before term start date."}
                )

            # If term has ended, is_current should be False
            if self.term_end < timezone.now().date() and self.is_current:
                raise ValidationError(
                    {"is_current": ("Cannot be marked as current when term has ended.")}
                )


class PersonDistrict(models.Model):
    """Many-to-many relationship between Person and District."""

    ASSIGNMENT_METHOD_CHOICES = [
        ("manual", "Manual Assignment"),
        ("voter_record", "Voter Record"),
        ("geocoding", "Geocoding"),
        ("zip_match", "ZIP Code Match"),
        ("import", "Data Import"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="person_districts"
    )
    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name="district_people"
    )

    # Assignment Information
    assignment_method = models.CharField(
        max_length=20, choices=ASSIGNMENT_METHOD_CHOICES
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    current_officeholder_name = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "person_districts"
        unique_together = [["person", "district"]]
        indexes = [
            models.Index(fields=["person", "district"]),
            models.Index(fields=["district", "assignment_method"]),
            models.Index(fields=["assigned_at"]),
            models.Index(fields=["confidence"]),
        ]

    def __str__(self) -> str:
        return f"{self.person.full_name} - {self.district.district_code}"

    def clean(self) -> None:
        """Validate the PersonDistrict instance."""
        super().clean()

        # Sanitize text field
        if self.current_officeholder_name:
            sanitized_value = sanitize_text_field(self.current_officeholder_name)
            self.current_officeholder_name = sanitized_value
            validate_text_content(sanitized_value, "current_officeholder_name")

        # Validate confidence is within valid range (0-100)
        if self.confidence is not None:
            if not (0 <= self.confidence <= 100):
                raise ValidationError(
                    {"confidence": "Confidence must be between 0 and 100."}
                )
