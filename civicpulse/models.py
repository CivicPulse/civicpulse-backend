import re
import uuid
from typing import Optional

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

    def by_location(self, state: str = None, zip_code: str = None) -> QuerySet:
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

    def by_age_range(self, min_age: int = None, max_age: int = None) -> QuerySet:
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
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.filter(contact_attempts__contact_date__gte=cutoff_date).distinct()


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
    campaign = models.CharField(max_length=100, blank=True)
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
        text_fields = ["notes", "campaign", "event"]
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
            ten_years_ago = timezone.now() - timezone.timedelta(days=3650)
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
                        "Follow-up date cannot be in the past when "
                        "follow-up is required."
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
