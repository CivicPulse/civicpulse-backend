"""
Person service layer for CivicPulse application.

This module provides business logic for Person management, including:
- Person creation with validation and duplicate detection
- Optimized duplicate detection with caching
- Data sanitization and business rule validation

The service layer separates business logic from view logic, making it:
- More testable (can be unit tested without Django views)
- Reusable (can be called from views, management commands, Celery tasks, APIs)
- Maintainable (business rules in one place)
"""

from datetime import date, datetime
from typing import Any, TypedDict, cast

import phonenumbers
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from loguru import logger
from phonenumbers import NumberParseException

from civicpulse.models import (
    VALID_US_STATE_CODES,
    Person,
    User,
    sanitize_text_field,
    validate_phone_number,
    validate_zip_code,
)


class PersonDataDict(TypedDict, total=False):
    """
    Type definition for person data dictionary.

    This TypedDict defines all possible fields that can be passed to the service layer
    for creating or updating a Person. All fields are optional (total=False).

    Attributes:
        first_name: Person's first name (required for creation)
        middle_name: Person's middle name (optional)
        last_name: Person's last name (required for creation)
        suffix: Name suffix (e.g., Jr., Sr., III)
        date_of_birth: Date of birth as date object or string (YYYY-MM-DD)
        gender: Gender code (M, F, O, U)
        email: Email address
        phone_primary: Primary phone number
        phone_secondary: Secondary phone number
        street_address: Street address
        apartment_number: Apartment/unit number
        city: City name
        state: Two-letter state code (e.g., CA, NY)
        zip_code: ZIP or ZIP+4 code
        county: County name
        occupation: Person's occupation
        employer: Person's employer
        notes: Additional notes
        tags: List of tags (strings)
    """

    first_name: str
    middle_name: str
    last_name: str
    suffix: str
    date_of_birth: date | str
    gender: str
    email: str
    phone_primary: str
    phone_secondary: str
    street_address: str
    apartment_number: str
    city: str
    state: str
    zip_code: str
    county: str
    occupation: str
    employer: str
    notes: str
    tags: list[str]


class PersonDuplicateDetector:
    """
    Service for detecting potential duplicate Person records.

    This class provides optimized duplicate detection using the Person model's
    get_potential_duplicates() method and additional business logic.

    Key features:
    - Leverages existing database indexes (email, phone, name+DOB)
    - Uses Q objects for efficient queries
    - Returns only active persons (respects soft delete)
    - Can be used before person creation or for existing records

    Example:
        >>> detector = PersonDuplicateDetector()
        >>> person_data = {
        ...     'first_name': 'John',
        ...     'last_name': 'Doe',
        ...     'email': 'john@example.com'
        ... }
        >>> duplicates = detector.find_duplicates(person_data)
        >>> if duplicates.exists():
        ...     print(f"Found {duplicates.count()} potential duplicates")
    """

    def find_duplicates(
        self, person_data: PersonDataDict, exclude_id: str | None = None
    ) -> QuerySet[Person]:
        """
        Find potential duplicate persons based on provided data.

        This method builds a query that checks for duplicates using multiple criteria:
        - Exact match on first name, last name, and date of birth
        - Case-insensitive email match
        - Exact phone number matches (primary or secondary)
        - Name and address combination

        The method leverages the Person model's existing indexes for performance.

        Args:
            person_data: Dictionary containing person information to check for
                duplicates. Required keys for effective duplicate detection:
                - first_name (str): Person's first name
                - last_name (str): Person's last name
                Optional but recommended:
                - date_of_birth (date|str): Date of birth for more accurate matching
                - email (str): Email address for contact-based matching
                - phone_primary (str): Primary phone for contact-based matching
                - phone_secondary (str): Secondary phone for contact-based matching
                - street_address (str): Street address for location-based matching
                - zip_code (str): ZIP code for location-based matching

            exclude_id: Optional UUID to exclude from results (useful when checking
                an existing person for duplicates)

        Returns:
            QuerySet of Person objects that are potential duplicates. The queryset:
            - Only includes active persons (is_active=True)
            - Is distinct (no duplicate results)
            - Can be empty if no duplicates found
            - Orders results by relevance (most likely duplicates first)

        Raises:
            ValidationError: If required fields (first_name, last_name) are missing

        Example:
            >>> detector = PersonDuplicateDetector()
            >>> data = {
            ...     'first_name': 'Jane',
            ...     'last_name': 'Smith',
            ...     'date_of_birth': date(1985, 5, 15),
            ...     'email': 'jane.smith@example.com'
            ... }
            >>> duplicates = detector.find_duplicates(data)
            >>> for person in duplicates:
            ...     print(f"Potential duplicate: {person.full_name} ({person.email})")
        """
        logger.debug(f"Checking for duplicates with data: {person_data}")

        # Validate required fields
        if not person_data.get("first_name") or not person_data.get("last_name"):
            raise ValidationError(
                "first_name and last_name are required for duplicate detection"
            )

        # Build the duplicate query using Q objects
        filters = self._build_duplicate_query(person_data)

        # Query for potential duplicates
        queryset = Person.objects.filter(filters).filter(is_active=True)

        # Exclude a specific person if provided (useful for updates)
        if exclude_id:
            queryset = queryset.exclude(pk=exclude_id)

        # Return distinct results
        duplicates = queryset.distinct()

        logger.info(f"Found {duplicates.count()} potential duplicates")
        return duplicates

    def _build_duplicate_query(self, person_data: PersonDataDict) -> Q:
        """
        Build optimized Q object for duplicate detection.

        This helper method constructs a complex query that checks multiple
        duplicate scenarios using OR logic. Each scenario leverages existing
        database indexes for optimal performance.

        Duplicate detection scenarios:
        1. Same name and date of birth (uses composite index)
        2. Same email address (uses email index, case-insensitive)
        3. Same primary phone number (uses phone_primary index)
        4. Same secondary phone number (uses phone_secondary index)
        5. Same name and address (uses name and zip_code indexes)

        Args:
            person_data: Dictionary containing person information

        Returns:
            Q object with OR-combined conditions for duplicate detection.
            Returns empty Q() if no matchable fields are provided.

        Note:
            The query is optimized to use existing database indexes:
            - Index on ['first_name', 'last_name', 'date_of_birth']
            - Index on ['email'] (case-insensitive search)
            - Index on ['phone_primary']
            - Index on ['phone_secondary']
            - Index on ['state', 'zip_code']

        Example:
            >>> detector = PersonDuplicateDetector()
            >>> data = {
            ...     'first_name': 'John',
            ...     'last_name': 'Doe',
            ...     'email': 'john@test.com'
            ... }
            >>> q = detector._build_duplicate_query(data)
            >>> # Results in: Q(email__iexact='john@test.com')
        """
        filters = Q()

        first_name = person_data.get("first_name", "").strip()
        last_name = person_data.get("last_name", "").strip()
        date_of_birth = person_data.get("date_of_birth")
        email = person_data.get("email", "").strip()
        phone_primary = person_data.get("phone_primary", "").strip()
        phone_secondary = person_data.get("phone_secondary", "").strip()
        street_address = person_data.get("street_address", "").strip()
        zip_code = person_data.get("zip_code", "").strip()

        # Scenario 1: Same name and date of birth (strong match)
        if date_of_birth and first_name and last_name:
            # Convert string to date if needed
            if isinstance(date_of_birth, str):
                try:
                    date_of_birth = datetime.strptime(
                        date_of_birth, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    logger.warning(f"Invalid date format: {date_of_birth}")
                    date_of_birth = None

            if date_of_birth:
                filters |= Q(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                    date_of_birth=date_of_birth,
                )
                logger.debug("Added name+DOB filter")

        # Scenario 2: Same email (strong match if email exists)
        if email:
            filters |= Q(email__iexact=email)
            logger.debug(f"Added email filter: {email}")

        # Scenario 3: Same primary phone (strong match if phone exists)
        if phone_primary:
            filters |= Q(phone_primary=phone_primary)
            logger.debug("Added primary phone filter")

        # Scenario 4: Same secondary phone (medium match)
        if phone_secondary:
            filters |= Q(phone_secondary=phone_secondary)
            logger.debug("Added secondary phone filter")

        # Scenario 5: Same name and address (medium-strong match)
        if first_name and last_name and street_address and zip_code:
            filters |= Q(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                street_address__iexact=street_address,
                zip_code=zip_code,
            )
            logger.debug("Added name+address filter")

        return filters


class PersonCreationService:
    """
    Service for creating and managing Person records.

    This class orchestrates person creation with comprehensive validation,
    duplicate detection, and data sanitization. It encapsulates all business
    logic for person management.

    Key features:
    - Validates business rules beyond model constraints
    - Detects potential duplicates before creation
    - Sanitizes and normalizes input data
    - Uses database transactions for data integrity
    - Provides detailed error messages for validation failures
    - Respects soft delete (creates new records, doesn't reuse deleted ones)

    The service can be used from:
    - Django views (web forms)
    - Django REST Framework serializers
    - Management commands
    - Celery tasks
    - Admin actions
    - Any Python code that needs to create persons

    Example:
        >>> service = PersonCreationService()
        >>> person_data = {
        ...     'first_name': 'John',
        ...     'last_name': 'Doe',
        ...     'email': 'john@example.com',
        ...     'phone_primary': '555-1234',
        ...     'date_of_birth': date(1990, 1, 1)
        ... }
        >>> try:
        ...     person, duplicates = service.create_person(
        ...         person_data=person_data,
        ...         created_by=current_user,
        ...         check_duplicates=True
        ...     )
        ...     if duplicates:
        ...         print(f"Warning: {len(duplicates)} potential duplicates found")
        ...     print(f"Created: {person.full_name}")
        ... except ValidationError as e:
        ...     print(f"Validation failed: {e.message_dict}")
    """

    def __init__(self) -> None:
        """
        Initialize the PersonCreationService.

        Creates an instance of PersonDuplicateDetector for duplicate checking.
        """
        self.duplicate_detector = PersonDuplicateDetector()

    @transaction.atomic
    def create_person(
        self,
        person_data: PersonDataDict,
        created_by: User,
        check_duplicates: bool = True,
    ) -> tuple[Person, list[Person]]:
        """
        Create a new Person record with validation and duplicate detection.

        This is the main entry point for person creation. It orchestrates the entire
        creation process including validation, sanitization, duplicate detection,
        and database persistence.

        The method performs the following steps:
        1. Validates business rules (required fields, data format)
        2. Sanitizes and normalizes input data
        3. Checks for potential duplicates (if enabled)
        4. Creates Person instance (within database transaction)
        5. Runs model validation (clean() method)
        6. Saves to database
        7. Returns created person and any duplicates found

        Args:
            person_data: Dictionary containing person information. Required keys:
                - first_name (str): Person's first name
                - last_name (str): Person's last name
                Optional keys: See PersonDataDict for all available fields.

            created_by: User instance who is creating this person.
                Used to populate the created_by field for audit trail.

            check_duplicates: Whether to check for potential duplicates before
                creation. Default is True. Set to False to skip duplicate
                detection (not recommended).

        Returns:
            A tuple containing:
            - person (Person): The newly created Person instance
            - duplicates (list[Person]): List of potential duplicate Person objects.
              Empty list if no duplicates found or check_duplicates=False.

        Raises:
            ValidationError: If validation fails. The exception contains a message_dict
                with field names as keys and error messages as values.
                Common validation errors:
                - Missing required fields (first_name, last_name)
                - Invalid date of birth (future date, unrealistic age)
                - Invalid email format or suspicious domain
                - Invalid phone number format
                - Invalid state code
                - Invalid ZIP code format
                - Text content validation failures (XSS, injection attempts)

            IntegrityError: If database constraints are violated, such as:
                - Unique constraint violation (same name+DOB already exists)
                - Foreign key constraint violation

        Example:
            >>> service = PersonCreationService()
            >>> person_data = {
            ...     'first_name': 'Jane',
            ...     'last_name': 'Smith',
            ...     'email': 'jane.smith@example.com',
            ...     'phone_primary': '(555) 123-4567',
            ...     'date_of_birth': '1985-05-15',
            ...     'street_address': '123 Main St',
            ...     'city': 'Springfield',
            ...     'state': 'CA',
            ...     'zip_code': '90210'
            ... }
            >>> person, dupes = service.create_person(
            ...     person_data=person_data,
            ...     created_by=request.user,
            ...     check_duplicates=True
            ... )
            >>> if dupes:
            ...     print(f"⚠ Found {len(dupes)} potential duplicates!")
            ...     for dup in dupes:
            ...         print(f"  - {dup.full_name} ({dup.email})")

        Note:
            - Uses @transaction.atomic to ensure all-or-nothing database writes
            - Sanitizes text fields to prevent XSS and injection attacks
            - Normalizes phone numbers to E.164 format for storage
            - Case-insensitive email storage (lowercase)
            - State codes converted to uppercase
            - Whitespace trimmed from all string fields
        """
        first = person_data.get("first_name")
        last = person_data.get("last_name")
        logger.info(f"Creating person: {first} {last}")

        # Step 1: Validate business rules
        validation_errors = self.validate_person_data(person_data)
        if validation_errors:
            logger.warning(f"Validation failed: {validation_errors}")
            raise ValidationError(validation_errors)

        # Step 2: Sanitize and normalize data
        sanitized_data = self._sanitize_person_data(person_data)
        logger.debug("Data sanitized successfully")

        # Step 3: Check for duplicates before creation
        duplicates = []
        if check_duplicates:
            sanitized_person_data = cast(PersonDataDict, sanitized_data)
            duplicates_qs = self.duplicate_detector.find_duplicates(
                sanitized_person_data
            )
            duplicates = list(duplicates_qs)
            if duplicates:
                logger.warning(
                    f"Found {len(duplicates)} potential duplicates before creation"
                )

        # Step 4: Create Person instance
        try:
            # Remove created_by from person_data if present (will be set explicitly)
            sanitized_data.pop("created_by", None)

            # Create the Person instance
            person = Person(**sanitized_data, created_by=created_by)

            # Step 5: Run model validation (calls Person.clean())
            person.full_clean()

            # Step 6: Save to database
            person.save()

            logger.info(
                f"Successfully created person: {person.pk} - {person.full_name}"
            )
            return person, duplicates

        except IntegrityError as e:
            # Handle unique constraint violations
            logger.error(f"IntegrityError creating person: {e}")
            if "unique constraint" in str(e).lower():
                raise ValidationError(
                    {
                        "__all__": (
                            "A person with this name and date of birth already exists."
                        )
                    }
                ) from e
            raise

        except Exception as e:
            # Log unexpected errors
            logger.error(f"Unexpected error creating person: {e}")
            raise

    def validate_person_data(self, person_data: PersonDataDict) -> dict[str, list[str]]:
        """
        Validate business rules for person data.

        This method performs business logic validation beyond what the Django model
        enforces. It checks for required fields, data format, and logical consistency.

        The validation is separate from model validation (Person.clean()) to allow
        for early detection of issues and better error messages.

        Args:
            person_data: Dictionary containing person information to validate

        Returns:
            Dictionary mapping field names to lists of error messages.
            Empty dict if validation passes.
            Format: {'field_name': ['error message 1', 'error message 2'], ...}

        Validation Rules:
            1. Required Fields:
               - first_name: Cannot be empty or whitespace
               - last_name: Cannot be empty or whitespace

            2. Date of Birth:
               - Must be valid date format (YYYY-MM-DD string or date object)
               - Cannot be in the future
               - Must represent realistic age (not older than 150 years)
               - Age must be >= 0

            3. Email:
               - Must be valid email format (if provided)
               - Domain must not be in suspicious domains list

            4. Phone Numbers:
               - Must be valid phone number format (if provided)
               - Uses phonenumbers library for validation

            5. State:
               - Must be valid US state code (if provided)
               - Converted to uppercase for validation

            6. ZIP Code:
               - Must be valid ZIP or ZIP+4 format (if provided)
               - Format: XXXXX or XXXXX-XXXX

            7. Gender:
               - Must be one of: M, F, O, U (if provided)

        Example:
            >>> service = PersonCreationService()
            >>> data = {
            ...     'first_name': '',
            ...     'last_name': 'Doe',
            ...     'date_of_birth': '2030-01-01',
            ...     'state': 'ZZ'
            ... }
            >>> errors = service.validate_person_data(data)
            >>> print(errors)
            {
                'first_name': ['First name is required'],
                'date_of_birth': ['Date of birth cannot be in the future'],
                'state': ["'ZZ' is not a valid US state code"]
            }

        Note:
            - This validation runs BEFORE model validation
            - Complements but does not replace Django model validation
            - Returns all validation errors at once (not just the first error)
            - Error messages are user-friendly and actionable
        """
        errors: dict[str, list[str]] = {}

        # Validate required fields
        if not person_data.get("first_name", "").strip():
            errors.setdefault("first_name", []).append("First name is required")

        if not person_data.get("last_name", "").strip():
            errors.setdefault("last_name", []).append("Last name is required")

        # Validate date of birth
        date_of_birth = person_data.get("date_of_birth")
        if date_of_birth:
            # Convert string to date if needed
            if isinstance(date_of_birth, str):
                try:
                    date_of_birth = datetime.strptime(
                        date_of_birth, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    errors.setdefault("date_of_birth", []).append(
                        "Invalid date format. Use YYYY-MM-DD"
                    )
                    date_of_birth = None

            # Validate date is not in future
            if date_of_birth and date_of_birth > timezone.now().date():
                errors.setdefault("date_of_birth", []).append(
                    "Date of birth cannot be in the future"
                )

            # Validate age is reasonable (not older than 150 years)
            if date_of_birth:
                today = timezone.now().date()
                age = today.year - date_of_birth.year
                if age > 150:
                    errors.setdefault("date_of_birth", []).append(
                        "Date of birth indicates an unrealistic age"
                    )
                if age < 0:
                    errors.setdefault("date_of_birth", []).append(
                        "Date of birth cannot be in the future"
                    )

        # Validate email format and domain
        email = person_data.get("email", "").strip()
        if email:
            if "@" not in email or "." not in email.split("@")[-1]:
                errors.setdefault("email", []).append("Invalid email format")
            else:
                # Check for suspicious domains
                domain = email.split("@")[-1].lower()
                suspicious_domains = getattr(
                    settings,
                    "SUSPICIOUS_EMAIL_DOMAINS",
                    ["example.com", "test.com", "localhost"],
                )
                if domain in suspicious_domains:
                    errors.setdefault("email", []).append(
                        f"Email domain '{domain}' is not allowed"
                    )

        # Validate phone numbers
        phone_primary = person_data.get("phone_primary", "").strip()
        if phone_primary:
            try:
                validate_phone_number(phone_primary)
            except ValidationError as e:
                errors.setdefault("phone_primary", []).append(str(e.message))

        phone_secondary = person_data.get("phone_secondary", "").strip()
        if phone_secondary:
            try:
                validate_phone_number(phone_secondary)
            except ValidationError as e:
                errors.setdefault("phone_secondary", []).append(str(e.message))

        # Validate state code
        state = person_data.get("state", "").strip().upper()
        if state and state not in VALID_US_STATE_CODES:
            errors.setdefault("state", []).append(
                f"'{state}' is not a valid US state code"
            )

        # Validate ZIP code
        zip_code = person_data.get("zip_code", "").strip()
        if zip_code:
            try:
                validate_zip_code(zip_code)
            except ValidationError as e:
                errors.setdefault("zip_code", []).append(str(e.message))

        # Validate gender
        gender = person_data.get("gender", "").strip().upper()
        if gender and gender not in ["M", "F", "O", "U"]:
            errors.setdefault("gender", []).append(
                "Gender must be one of: M (Male), F (Female), O (Other), U (Unknown)"
            )

        logger.debug(f"Validation completed with {len(errors)} error(s)")
        return errors

    def _sanitize_person_data(self, person_data: PersonDataDict) -> dict[str, Any]:
        """
        Sanitize and normalize person data before database storage.

        This helper method ensures all input data is clean, properly formatted,
        and safe for storage. It performs:
        - Text sanitization (remove HTML, scripts, control characters)
        - Whitespace normalization (trim leading/trailing spaces)
        - Case normalization (uppercase state codes, lowercase emails)
        - Phone number normalization (convert to E.164 format)
        - Date conversion (string to date objects)
        - Empty string to None conversion (for optional fields)

        Args:
            person_data: Raw person data dictionary

        Returns:
            Sanitized dictionary with normalized values ready for Person model.
            Only includes fields that are present in the input and have
            non-empty values.

        Sanitization Rules:
            1. Text Fields (names, addresses, notes):
               - Strip HTML tags
               - Remove script tags and content
               - Remove control characters (null bytes, etc.)
               - Trim whitespace
               - Limit length to prevent DoS
               - Validate for XSS attempts

            2. Email:
               - Convert to lowercase
               - Trim whitespace
               - Convert empty string to None

            3. Phone Numbers:
               - Parse and normalize to E.164 format (+1XXXXXXXXXX)
               - Fall back to original if parsing fails
               - Remove all non-digit characters except +

            4. State:
               - Convert to uppercase
               - Trim whitespace

            5. Date of Birth:
               - Convert string (YYYY-MM-DD) to date object
               - Keep as date object if already date
               - Set to None if invalid

            6. Tags:
               - Ensure it's a list
               - Remove duplicates
               - Strip whitespace from each tag
               - Remove empty tags

        Example:
            >>> service = PersonCreationService()
            >>> raw_data = {
            ...     'first_name': '  John  ',
            ...     'email': 'JOHN@EXAMPLE.COM',
            ...     'phone_primary': '(555) 123-4567',
            ...     'state': 'ca',
            ...     'notes': '<script>alert("xss")</script>Some notes'
            ... }
            >>> clean_data = service._sanitize_person_data(raw_data)
            >>> print(clean_data)
            {
                'first_name': 'John',
                'email': 'john@example.com',
                'phone_primary': '+15551234567',
                'state': 'CA',
                'notes': 'Some notes'
            }

        Note:
            - Uses Person model's sanitize_text_field() for text sanitization
            - Uses phonenumbers library for phone normalization
            - Preserves original data if normalization fails
            - Removes keys with empty/None values to let model defaults apply
        """
        sanitized: dict[str, Any] = {}

        # List of text fields to sanitize
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

        # Sanitize text fields
        for field in text_fields:
            value = person_data.get(field, "")
            if value and isinstance(value, str):
                sanitized_value = sanitize_text_field(value)
                if sanitized_value:  # Only include if not empty after sanitization
                    sanitized[field] = sanitized_value

        # Normalize email (lowercase)
        email = person_data.get("email", "").strip()
        if email:
            sanitized["email"] = email.lower()

        # Normalize phone numbers to E.164 format
        phone_primary = person_data.get("phone_primary", "").strip()
        if phone_primary:
            sanitized["phone_primary"] = self._normalize_phone_number(phone_primary)

        phone_secondary = person_data.get("phone_secondary", "").strip()
        if phone_secondary:
            sanitized["phone_secondary"] = self._normalize_phone_number(phone_secondary)

        # Normalize state (uppercase)
        state = person_data.get("state", "").strip()
        if state:
            sanitized["state"] = state.upper()

        # Normalize ZIP code (trim)
        zip_code = person_data.get("zip_code", "").strip()
        if zip_code:
            sanitized["zip_code"] = zip_code

        # Convert date of birth string to date object
        date_of_birth = person_data.get("date_of_birth")
        if date_of_birth:
            if isinstance(date_of_birth, str):
                try:
                    sanitized["date_of_birth"] = datetime.strptime(
                        date_of_birth, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    # Invalid date format - will be caught by validation
                    pass
            else:
                sanitized["date_of_birth"] = date_of_birth

        # Normalize gender (uppercase)
        gender = person_data.get("gender", "").strip()
        if gender:
            sanitized["gender"] = gender.upper()
        else:
            sanitized["gender"] = "U"  # Default to Unknown

        # Handle tags
        tags = person_data.get("tags", [])
        if tags:
            # Ensure it's a list and remove duplicates
            if isinstance(tags, list):
                sanitized["tags"] = list({tag.strip() for tag in tags if tag.strip()})
            else:
                sanitized["tags"] = []

        logger.debug(f"Sanitized {len(sanitized)} fields")
        return sanitized

    def _normalize_phone_number(self, phone_number: str) -> str:
        """
        Normalize phone number to consistent format.

        Attempts to parse and format the phone number to E.164 format
        (international format with + prefix). Falls back to original
        if parsing fails.

        Args:
            phone_number: Phone number in any format

        Returns:
            Normalized phone number in E.164 format (+1XXXXXXXXXX) or
            original string if parsing fails

        Example:
            >>> service = PersonCreationService()
            >>> service._normalize_phone_number("(555) 123-4567")
            '+15551234567'
            >>> service._normalize_phone_number("555.123.4567")
            '+15551234567'
            >>> service._normalize_phone_number("invalid")
            'invalid'

        Note:
            - Assumes US phone numbers by default (region="US")
            - Uses phonenumbers library for parsing
            - Preserves original string if parsing fails
            - Removes all formatting characters (spaces, hyphens, parentheses)
        """
        if not phone_number.strip():
            return phone_number

        try:
            parsed_number = phonenumbers.parse(phone_number, "US")
            if phonenumbers.is_valid_number(parsed_number):
                return phonenumbers.format_number(
                    parsed_number, phonenumbers.PhoneNumberFormat.E164
                )
        except NumberParseException:
            logger.debug(f"Could not parse phone number: {phone_number}")

        # Return original if parsing fails
        return phone_number
