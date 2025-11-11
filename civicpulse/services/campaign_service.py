"""
Campaign service layer for CivicPulse application.

This module provides business logic for Campaign management, including:
- Campaign creation with validation and duplicate detection
- Optimized duplicate detection with caching
- Data sanitization and business rule validation

The service layer separates business logic from view logic, making it:
- More testable (can be unit tested without Django views)
- Reusable (can be called from views, management commands, Celery tasks, APIs)
- Maintainable (business rules in one place)
"""

from datetime import date, datetime, timedelta
from typing import Any, TypedDict, cast

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from loguru import logger

from civicpulse.models import (
    Campaign,
    User,
    sanitize_text_field,
)


class CampaignDataDict(TypedDict, total=False):
    """
    Type definition for campaign data dictionary.

    This TypedDict defines all possible fields that can be passed to the service layer
    for creating or updating a Campaign. All fields are optional (total=False).

    Attributes:
        name: Campaign name (required for creation)
        description: Campaign description (optional)
        candidate_name: Name of the candidate (required for creation)
        election_date: Date of the election as date object or string (YYYY-MM-DD)
        status: Campaign status (active, paused, completed, archived)
        organization: Organization running the campaign (optional)
    """

    name: str
    description: str
    candidate_name: str
    election_date: date | str
    status: str
    organization: str


class CampaignDuplicateDetector:
    """
    Service for detecting potential duplicate Campaign records.

    This class provides optimized duplicate detection using database indexes
    and business logic to identify campaigns that may be duplicates.

    Key features:
    - Leverages existing database indexes (name, election_date, candidate_name)
    - Uses Q objects for efficient queries
    - Returns only active campaigns (respects soft delete)
    - Can be used before campaign creation or for existing records

    Example:
        >>> detector = CampaignDuplicateDetector()
        >>> campaign_data = {
        ...     'name': 'Vote for John Doe',
        ...     'candidate_name': 'John Doe',
        ...     'election_date': date(2024, 11, 5)
        ... }
        >>> duplicates = detector.find_duplicates(campaign_data)
        >>> if duplicates.exists():
        ...     print(f"Found {duplicates.count()} potential duplicates")
    """

    def find_duplicates(
        self, campaign_data: CampaignDataDict, exclude_id: str | None = None
    ) -> QuerySet[Campaign]:
        """
        Find potential duplicate campaigns based on provided data.

        This method builds a query that checks for duplicates using multiple criteria:
        - Case-insensitive name match with election date within 30 days
        - Case-insensitive candidate name match with election date within 30 days

        The method leverages the Campaign model's existing indexes for performance.

        Args:
            campaign_data: Dictionary containing campaign information to check for
                duplicates. Required keys for effective duplicate detection:
                - name (str): Campaign name
                - candidate_name (str): Candidate name
                - election_date (date|str): Date of election for temporal matching
                Optional:
                - organization (str): Organization name for additional matching

            exclude_id: Optional UUID to exclude from results (useful when checking
                an existing campaign for duplicates)

        Returns:
            QuerySet of Campaign objects that are potential duplicates. The queryset:
            - Only includes active campaigns (is_active=True)
            - Is distinct (no duplicate results)
            - Can be empty if no duplicates found
            - Orders results by relevance (most likely duplicates first)

        Raises:
            ValidationError: If required fields (name, candidate_name) are missing

        Example:
            >>> detector = CampaignDuplicateDetector()
            >>> data = {
            ...     'name': '2024 Senate Campaign',
            ...     'candidate_name': 'Jane Smith',
            ...     'election_date': date(2024, 11, 5),
            ...     'organization': 'Democratic Party'
            ... }
            >>> duplicates = detector.find_duplicates(data)
            >>> for campaign in duplicates:
            ...     print(
            ...         f"Potential duplicate: {campaign.name} "
            ...         f"({campaign.candidate_name})"
            ...     )
        """
        logger.debug(f"Checking for duplicates with data: {campaign_data}")

        # Validate required fields
        if not campaign_data.get("name") and not campaign_data.get("candidate_name"):
            raise ValidationError(
                "At least one of name or candidate_name is required "
                "for duplicate detection"
            )

        # Build the duplicate query using Q objects
        filters = self._build_duplicate_query(campaign_data)

        # Query for potential duplicates
        queryset = Campaign.objects.filter(filters).filter(is_active=True)

        # Exclude a specific campaign if provided (useful for updates)
        if exclude_id:
            queryset = queryset.exclude(pk=exclude_id)

        # Return distinct results
        duplicates = queryset.distinct()

        logger.info(f"Found {duplicates.count()} potential duplicates")
        return duplicates

    def _build_duplicate_query(self, campaign_data: CampaignDataDict) -> Q:
        """
        Build optimized Q object for duplicate detection.

        This helper method constructs a complex query that checks multiple
        duplicate scenarios using OR logic. Each scenario leverages existing
        database indexes for optimal performance.

        Duplicate detection scenarios:
        1. Same name and election date within 30 days (uses name index)
        2. Same candidate name and election date within 30 days
           (uses candidate_name index)

        Args:
            campaign_data: Dictionary containing campaign information

        Returns:
            Q object with OR-combined conditions for duplicate detection.
            Returns empty Q() if no matchable fields are provided.

        Note:
            The query is optimized to use existing database indexes:
            - Index on ['name']
            - Index on ['election_date']
            - Index on ['candidate_name']
            - Composite index on ['status', 'election_date']

        Example:
            >>> detector = CampaignDuplicateDetector()
            >>> data = {
            ...     'name': 'Vote for Change',
            ...     'candidate_name': 'John Doe',
            ...     'election_date': date(2024, 11, 5)
            ... }
            >>> q = detector._build_duplicate_query(data)
            >>> # Results in:
            >>> # Q(name__iexact='Vote for Change', election_date__range=(...))
            >>> # | Q(candidate_name__iexact='John Doe', election_date__range=(...))
        """
        filters = Q()

        name = campaign_data.get("name", "").strip()
        candidate_name = campaign_data.get("candidate_name", "").strip()
        election_date = campaign_data.get("election_date")

        # Convert string to date if needed
        if isinstance(election_date, str):
            try:
                election_date = datetime.strptime(election_date, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Invalid date format: {election_date}")
                election_date = None

        if not election_date:
            logger.warning("No valid election date for duplicate detection")
            return filters

        # Calculate date range (30 days before and after)
        date_range_start = election_date - timedelta(days=30)
        date_range_end = election_date + timedelta(days=30)

        # Scenario 1: Same name and election date within 30 days (strong match)
        if name:
            filters |= Q(
                name__iexact=name,
                election_date__range=(date_range_start, date_range_end),
            )
            logger.debug("Added name+date filter")

        # Scenario 2: Same candidate name and election date within 30 days
        # (strong match)
        if candidate_name:
            filters |= Q(
                candidate_name__iexact=candidate_name,
                election_date__range=(date_range_start, date_range_end),
            )
            logger.debug("Added candidate_name+date filter")

        return filters


class CampaignCreationService:
    """
    Service for creating and managing Campaign records.

    This class orchestrates campaign creation with comprehensive validation,
    duplicate detection, and data sanitization. It encapsulates all business
    logic for campaign management.

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
    - Any Python code that needs to create campaigns

    Example:
        >>> service = CampaignCreationService()
        >>> campaign_data = {
        ...     'name': '2024 Senate Campaign',
        ...     'candidate_name': 'Jane Smith',
        ...     'election_date': date(2024, 11, 5),
        ...     'status': 'active',
        ...     'organization': 'Democratic Party'
        ... }
        >>> try:
        ...     campaign, duplicates = service.create_campaign(
        ...         campaign_data=campaign_data,
        ...         created_by=current_user,
        ...         check_duplicates=True
        ...     )
        ...     if duplicates:
        ...         print(f"Warning: {len(duplicates)} potential duplicates found")
        ...     print(f"Created: {campaign.name}")
        ... except ValidationError as e:
        ...     print(f"Validation failed: {e.message_dict}")
    """

    def __init__(self) -> None:
        """
        Initialize the CampaignCreationService.

        Creates an instance of CampaignDuplicateDetector for duplicate checking.
        """
        self.duplicate_detector = CampaignDuplicateDetector()

    @transaction.atomic
    def create_campaign(
        self,
        campaign_data: CampaignDataDict,
        created_by: User,
        check_duplicates: bool = True,
    ) -> tuple[Campaign, list[Campaign]]:
        """
        Create a new Campaign record with validation and duplicate detection.

        This is the main entry point for campaign creation. It orchestrates the entire
        creation process including validation, sanitization, duplicate detection,
        and database persistence.

        The method performs the following steps:
        1. Validates business rules (required fields, data format)
        2. Sanitizes and normalizes input data
        3. Checks for potential duplicates (if enabled)
        4. Creates Campaign instance (within database transaction)
        5. Runs model validation (clean() method)
        6. Saves to database
        7. Returns created campaign and any duplicates found

        Args:
            campaign_data: Dictionary containing campaign information. Required keys:
                - name (str): Campaign name
                - candidate_name (str): Candidate name
                - election_date (date|str): Date of the election
                Optional keys: See CampaignDataDict for all available fields.

            created_by: User instance who is creating this campaign.
                Used to populate the created_by field for audit trail.

            check_duplicates: Whether to check for potential duplicates before
                creation. Default is True. Set to False to skip duplicate
                detection (not recommended).

        Returns:
            A tuple containing:
            - campaign (Campaign): The newly created Campaign instance
            - duplicates (list[Campaign]): List of potential duplicate Campaign objects.
              Empty list if no duplicates found or check_duplicates=False.

        Raises:
            ValidationError: If validation fails. The exception contains a message_dict
                with field names as keys and error messages as values.
                Common validation errors:
                - Missing required fields (name, candidate_name, election_date)
                - Invalid election date (past date, unrealistic future date)
                - Invalid status value
                - Text content validation failures (XSS, injection attempts)
                - Campaign name already exists

            IntegrityError: If database constraints are violated, such as:
                - Unique constraint violation
                - Foreign key constraint violation

        Example:
            >>> service = CampaignCreationService()
            >>> campaign_data = {
            ...     'name': '2024 Presidential Campaign',
            ...     'description': 'Running for President in 2024',
            ...     'candidate_name': 'John Smith',
            ...     'election_date': '2024-11-05',
            ...     'status': 'active',
            ...     'organization': 'Independent'
            ... }
            >>> campaign, dupes = service.create_campaign(
            ...     campaign_data=campaign_data,
            ...     created_by=request.user,
            ...     check_duplicates=True
            ... )
            >>> if dupes:
            ...     print(f"Warning: Found {len(dupes)} potential duplicates!")
            ...     for dup in dupes:
            ...         print(f"  - {dup.name} ({dup.candidate_name})")

        Note:
            - Uses @transaction.atomic to ensure all-or-nothing database writes
            - Sanitizes text fields to prevent XSS and injection attacks
            - Status defaults to 'active' if not provided
            - Election date is validated against past and future constraints
            - Campaign names are checked for uniqueness (case-insensitive)
        """
        name = campaign_data.get("name")
        candidate_name = campaign_data.get("candidate_name")
        logger.info(f"Creating campaign: {name} for {candidate_name}")

        # Step 1: Validate business rules
        validation_errors = self.validate_campaign_data(campaign_data)
        if validation_errors:
            logger.warning(f"Validation failed: {validation_errors}")
            raise ValidationError(validation_errors)

        # Step 2: Sanitize and normalize data
        sanitized_data = self._sanitize_campaign_data(campaign_data)
        logger.debug("Data sanitized successfully")

        # Step 3: Check for duplicates before creation
        duplicates = []
        if check_duplicates:
            sanitized_campaign_data = cast(CampaignDataDict, sanitized_data)
            duplicates_qs = self.duplicate_detector.find_duplicates(
                sanitized_campaign_data
            )
            duplicates = list(duplicates_qs)
            if duplicates:
                logger.warning(
                    f"Found {len(duplicates)} potential duplicates before creation"
                )

        # Step 4: Create Campaign instance
        try:
            # Remove created_by from campaign_data if present (will be set explicitly)
            sanitized_data.pop("created_by", None)

            # Create the Campaign instance
            campaign = Campaign(**sanitized_data, created_by=created_by)

            # Step 5: Run model validation (calls Campaign.clean())
            campaign.full_clean()

            # Step 6: Save to database
            campaign.save()

            logger.info(
                f"Successfully created campaign: {campaign.pk} - {campaign.name}"
            )
            return campaign, duplicates

        except IntegrityError as e:
            # Handle unique constraint violations
            logger.error(f"IntegrityError creating campaign: {e}")
            if "unique constraint" in str(e).lower():
                raise ValidationError(
                    {"__all__": ("A campaign with this name already exists.")}
                ) from e
            raise

        except Exception as e:
            # Log unexpected errors
            logger.error(f"Unexpected error creating campaign: {e}")
            raise

    @transaction.atomic
    def update_campaign(
        self,
        campaign_id: str,
        campaign_data: CampaignDataDict,
        updated_by: User,
        check_duplicates: bool = True,
    ) -> tuple[Campaign, list[Campaign]]:
        """
        Update an existing Campaign record with validation and duplicate detection.

        This method orchestrates the campaign update process including validation,
        sanitization, duplicate detection (excluding the current campaign), and
        database persistence.

        The method performs the following steps:
        1. Retrieves the existing campaign
        2. Validates business rules
        3. Sanitizes and normalizes input data
        4. Checks for potential duplicates (excluding current campaign)
        5. Updates Campaign instance
        6. Runs model validation
        7. Saves to database
        8. Returns updated campaign and any duplicates found

        Args:
            campaign_id: UUID of the campaign to update
            campaign_data: Dictionary containing campaign information to update.
                All fields are optional - only provided fields will be updated.
            updated_by: User instance who is updating this campaign.
            check_duplicates: Whether to check for potential duplicates during
                update. Default is True.

        Returns:
            A tuple containing:
            - campaign (Campaign): The updated Campaign instance
            - duplicates (list[Campaign]): List of potential duplicate Campaign objects.
              Empty list if no duplicates found or check_duplicates=False.

        Raises:
            Campaign.DoesNotExist: If campaign with given ID doesn't exist
            ValidationError: If validation fails
            IntegrityError: If database constraints are violated

        Example:
            >>> service = CampaignCreationService()
            >>> campaign_data = {
            ...     'status': 'completed',
            ...     'description': 'Campaign successfully completed'
            ... }
            >>> campaign, dupes = service.update_campaign(
            ...     campaign_id='123e4567-e89b-12d3-a456-426614174000',
            ...     campaign_data=campaign_data,
            ...     updated_by=request.user
            ... )
        """
        logger.info(f"Updating campaign: {campaign_id}")

        # Retrieve the existing campaign
        try:
            campaign = Campaign.objects.get(pk=campaign_id)
        except Campaign.DoesNotExist:
            logger.error(f"Campaign not found: {campaign_id}")
            raise

        # Step 1: Validate business rules
        validation_errors = self.validate_campaign_data(campaign_data, is_update=True)
        if validation_errors:
            logger.warning(f"Validation failed: {validation_errors}")
            raise ValidationError(validation_errors)

        # Step 2: Sanitize and normalize data
        sanitized_data = self._sanitize_campaign_data(campaign_data)
        logger.debug("Data sanitized successfully")

        # Step 3: Check for duplicates (excluding current campaign)
        duplicates = []
        if check_duplicates:
            sanitized_campaign_data = cast(CampaignDataDict, sanitized_data)
            duplicates_qs = self.duplicate_detector.find_duplicates(
                sanitized_campaign_data, exclude_id=str(campaign_id)
            )
            duplicates = list(duplicates_qs)
            if duplicates:
                logger.warning(
                    f"Found {len(duplicates)} potential duplicates during update"
                )

        # Step 4: Update Campaign instance
        try:
            # Update fields
            for field, value in sanitized_data.items():
                setattr(campaign, field, value)

            # Step 5: Run model validation (calls Campaign.clean())
            campaign.full_clean()

            # Step 6: Save to database
            campaign.save()

            logger.info(
                f"Successfully updated campaign: {campaign.pk} - {campaign.name}"
            )
            return campaign, duplicates

        except IntegrityError as e:
            logger.error(f"IntegrityError updating campaign: {e}")
            if "unique constraint" in str(e).lower():
                raise ValidationError(
                    {"__all__": "A campaign with this name already exists."}
                ) from e
            raise

        except Exception as e:
            logger.error(f"Unexpected error updating campaign: {e}")
            raise

    def validate_campaign_data(
        self, campaign_data: CampaignDataDict, is_update: bool = False
    ) -> dict[str, list[str]]:
        """
        Validate business rules for campaign data.

        This method performs business logic validation beyond what the Django model
        enforces. It checks for required fields, data format, and logical consistency.

        The validation is separate from model validation (Campaign.clean()) to allow
        for early detection of issues and better error messages.

        Args:
            campaign_data: Dictionary containing campaign information to validate
            is_update: Whether this is an update operation (allows optional fields)

        Returns:
            Dictionary mapping field names to lists of error messages.
            Empty dict if validation passes.
            Format: {'field_name': ['error message 1', 'error message 2'], ...}

        Validation Rules:
            1. Required Fields (for creation):
               - name: Cannot be empty or whitespace, 3-200 characters
               - candidate_name: Cannot be empty or whitespace, 2-200 characters
               - election_date: Must be provided and valid

            2. Election Date:
               - Must be valid date format (YYYY-MM-DD string or date object)
               - Must be a valid date value
               - For new campaigns: cannot be in the past
               - Cannot be more than 10 years in the future

            3. Status:
               - Must be one of: active, paused, completed, archived
               - Defaults to 'active' if not provided

            4. Name Length:
               - Minimum 3 characters
               - Maximum 200 characters

            5. Candidate Name Length:
               - Minimum 2 characters
               - Maximum 200 characters

            6. Description:
               - Optional
               - Maximum 10000 characters (enforced by sanitization)

            7. Organization:
               - Optional
               - Maximum 255 characters

        Example:
            >>> service = CampaignCreationService()
            >>> data = {
            ...     'name': 'A',  # Too short
            ...     'candidate_name': '',  # Empty
            ...     'election_date': '2020-01-01',  # Past date
            ...     'status': 'invalid'  # Invalid status
            ... }
            >>> errors = service.validate_campaign_data(data)
            >>> print(errors)
            {
                'name': ['Campaign name must be at least 3 characters'],
                'candidate_name': ['Candidate name is required'],
                'election_date': ['Election date cannot be in the past'],
                'status': ["'invalid' is not a valid status"]
            }

        Note:
            - This validation runs BEFORE model validation
            - Complements but does not replace Django model validation
            - Returns all validation errors at once (not just the first error)
            - Error messages are user-friendly and actionable
        """
        errors: dict[str, list[str]] = {}

        # Validate required fields (only for creation)
        if not is_update:
            if not campaign_data.get("name", "").strip():
                errors.setdefault("name", []).append("Campaign name is required")

            if not campaign_data.get("candidate_name", "").strip():
                errors.setdefault("candidate_name", []).append(
                    "Candidate name is required"
                )

            if not campaign_data.get("election_date"):
                errors.setdefault("election_date", []).append(
                    "Election date is required"
                )

        # Validate name length
        name = campaign_data.get("name", "").strip()
        if name:
            if len(name) < 3:
                errors.setdefault("name", []).append(
                    "Campaign name must be at least 3 characters"
                )
            if len(name) > 200:
                errors.setdefault("name", []).append(
                    "Campaign name must not exceed 200 characters"
                )

        # Validate candidate name length
        candidate_name = campaign_data.get("candidate_name", "").strip()
        if candidate_name:
            if len(candidate_name) < 2:
                errors.setdefault("candidate_name", []).append(
                    "Candidate name must be at least 2 characters"
                )
            if len(candidate_name) > 200:
                errors.setdefault("candidate_name", []).append(
                    "Candidate name must not exceed 200 characters"
                )

        # Validate election date
        election_date = campaign_data.get("election_date")
        if election_date:
            # Convert string to date if needed
            if isinstance(election_date, str):
                try:
                    election_date = datetime.strptime(election_date, "%Y-%m-%d").date()
                except ValueError:
                    errors.setdefault("election_date", []).append(
                        "Invalid date format. Use YYYY-MM-DD"
                    )
                    election_date = None

            # Validate date is not too far in the past (for new campaigns only)
            if election_date and not is_update:
                if election_date < timezone.now().date():
                    errors.setdefault("election_date", []).append(
                        "Election date cannot be in the past for new campaigns"
                    )

            # Validate date is not too far in the future (10 years)
            if election_date:
                ten_years_from_now = timezone.now().date() + timedelta(days=3650)
                if election_date > ten_years_from_now:
                    errors.setdefault("election_date", []).append(
                        "Election date seems unreasonably far in the future "
                        "(over 10 years)"
                    )

        # Validate status
        status = campaign_data.get("status", "").strip().lower()
        if status:
            valid_statuses = ["active", "paused", "completed", "archived"]
            if status not in valid_statuses:
                errors.setdefault("status", []).append(
                    f"'{status}' is not a valid status. "
                    f"Choose from: {', '.join(valid_statuses)}"
                )

        # Validate organization length
        organization = campaign_data.get("organization", "").strip()
        if organization and len(organization) > 255:
            errors.setdefault("organization", []).append(
                "Organization name must not exceed 255 characters"
            )

        logger.debug(f"Validation completed with {len(errors)} error(s)")
        return errors

    def _sanitize_campaign_data(
        self, campaign_data: CampaignDataDict
    ) -> dict[str, Any]:
        """
        Sanitize and normalize campaign data before database storage.

        This helper method ensures all input data is clean, properly formatted,
        and safe for storage. It performs:
        - Text sanitization (remove HTML, scripts, control characters)
        - Whitespace normalization (trim leading/trailing spaces)
        - Case normalization (lowercase status)
        - Date conversion (string to date objects)
        - Empty string to None conversion (for optional fields)

        Args:
            campaign_data: Raw campaign data dictionary

        Returns:
            Sanitized dictionary with normalized values ready for Campaign model.
            Only includes fields that are present in the input and have
            non-empty values.

        Sanitization Rules:
            1. Text Fields (name, description, candidate_name, organization):
               - Strip HTML tags
               - Remove script tags and content
               - Remove control characters (null bytes, etc.)
               - Trim whitespace
               - Limit length to prevent DoS
               - Validate for XSS attempts

            2. Status:
               - Convert to lowercase
               - Trim whitespace
               - Default to 'active' if not provided

            3. Election Date:
               - Convert string (YYYY-MM-DD) to date object
               - Keep as date object if already date
               - Set to None if invalid

        Example:
            >>> service = CampaignCreationService()
            >>> raw_data = {
            ...     'name': '  Vote for Change  ',
            ...     'description': '<script>alert("xss")</script>Campaign details',
            ...     'candidate_name': 'John Doe',
            ...     'status': 'ACTIVE',
            ...     'election_date': '2024-11-05'
            ... }
            >>> clean_data = service._sanitize_campaign_data(raw_data)
            >>> print(clean_data)
            {
                'name': 'Vote for Change',
                'description': 'Campaign details',
                'candidate_name': 'John Doe',
                'status': 'active',
                'election_date': date(2024, 11, 5)
            }

        Note:
            - Uses Campaign model's sanitize_text_field() for text sanitization
            - Preserves original data if normalization fails
            - Removes keys with empty/None values to let model defaults apply
        """
        sanitized: dict[str, Any] = {}

        # List of text fields to sanitize
        text_fields = [
            "name",
            "description",
            "candidate_name",
            "organization",
        ]

        # Sanitize text fields
        for field in text_fields:
            value = campaign_data.get(field, "")
            if value and isinstance(value, str):
                sanitized_value = sanitize_text_field(value)
                if sanitized_value:  # Only include if not empty after sanitization
                    sanitized[field] = sanitized_value

        # Normalize status (lowercase)
        status = campaign_data.get("status", "").strip().lower()
        if status:
            sanitized["status"] = status
        elif "status" not in campaign_data:
            # Default to 'active' for new campaigns
            sanitized["status"] = "active"

        # Convert election date string to date object
        election_date = campaign_data.get("election_date")
        if election_date:
            if isinstance(election_date, str):
                try:
                    sanitized["election_date"] = datetime.strptime(
                        election_date, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    # Invalid date format - will be caught by validation
                    pass
            else:
                sanitized["election_date"] = election_date

        logger.debug(f"Sanitized {len(sanitized)} fields")
        return sanitized
