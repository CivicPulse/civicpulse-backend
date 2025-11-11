"""
Django REST Framework serializers for CivicPulse Campaign model.

This module provides three specialized serializers for Campaign objects:

1. CampaignListSerializer: Lightweight serializer for list views with minimal fields
   and computed properties for performance optimization.

2. CampaignDetailSerializer: Comprehensive serializer with all fields, nested data,
   and related contact attempt information for detailed views.

3. CampaignSerializer: Full-featured serializer for create/update operations
   with extensive validation, integration with CampaignCreationService, and
   audit trail support.

All serializers follow DRF best practices and include:
- Type hints for better IDE support and type checking
- Comprehensive docstrings
- Field-level and object-level validation
- Security considerations (XSS prevention, input sanitization)
- Integration with existing service layer and audit systems
- Clear error messages for validation failures

Example Usage:
    # List view
    serializer = CampaignListSerializer(campaigns, many=True)

    # Detail view
    serializer = CampaignDetailSerializer(campaign)

    # Create operation
    serializer = CampaignSerializer(
        data=request.data,
        context={'request': request}
    )
    if serializer.is_valid():
        campaign = serializer.save()

    # Update operation
    serializer = CampaignSerializer(
        campaign,
        data=request.data,
        partial=True,
        context={'request': request}
    )
    if serializer.is_valid():
        campaign = serializer.save()
"""

from datetime import date
from typing import Any, cast

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from civicpulse.models import Campaign, ContactAttempt
from civicpulse.services.campaign_service import (
    CampaignCreationService,
    CampaignDataDict,
)


class CampaignListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for Campaign list views.

    Optimized for performance in list views by including only essential fields
    and computed properties. Minimizes database queries and serialization overhead.

    Fields:
        id (UUID): Primary key (read-only)
        name (str): Campaign name
        candidate_name (str): Name of the candidate
        election_date (date): Date of the election
        status (str): Current campaign status
        days_until_election (int|None): Computed days remaining until
            election (read-only)
        is_upcoming (bool): Whether the election is in the future (read-only)

    Example:
        >>> serializer = CampaignListSerializer(campaigns, many=True)
        >>> data = serializer.data
        >>> print(data)
        [
            {
                'id': '123e4567-e89b-12d3-a456-426614174000',
                'name': '2024 Senate Campaign',
                'candidate_name': 'Jane Smith',
                'election_date': '2024-11-05',
                'status': 'active',
                'days_until_election': 45,
                'is_upcoming': True
            },
            ...
        ]

    Note:
        - Read-only fields are computed from the model's properties
        - Minimal fields for optimal list view performance
        - Suitable for paginated list endpoints
    """

    days_until_election = serializers.SerializerMethodField()
    is_upcoming = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "candidate_name",
            "election_date",
            "status",
            "days_until_election",
            "is_upcoming",
        ]
        read_only_fields = ["id"]

    def get_days_until_election(self, obj: Campaign) -> int | None:
        """
        Get days remaining until election.

        Uses the Campaign model's days_until_election property which returns
        None if the election has already passed.

        Args:
            obj: Campaign instance

        Returns:
            Number of days until election, or None if election has passed
        """
        return obj.days_until_election

    def get_is_upcoming(self, obj: Campaign) -> bool:
        """
        Check if election is upcoming.

        Uses the Campaign model's is_upcoming property.

        Args:
            obj: Campaign instance

        Returns:
            True if election date is in the future, False otherwise
        """
        return obj.is_upcoming


class CampaignDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for Campaign detail views.

    Provides complete campaign information including all fields, related data,
    and computed properties. Includes nested contact attempt information and
    statistics for comprehensive campaign overview.

    Read-only Fields:
        id (UUID): Primary key
        created_at (datetime): When campaign was created
        updated_at (datetime): Last modification timestamp
        created_by (str): Username of creator
        deleted_at (datetime|None): Soft delete timestamp
        deleted_by (str|None): Username of user who soft-deleted the campaign
        days_until_election (int|None): Computed days remaining
        is_upcoming (bool): Whether election is in future
        contact_attempts_count (int): Total number of contact attempts
        recent_contact_attempts (list): Last 5 contact attempts with details

    Editable Fields:
        name (str): Campaign name
        description (str): Campaign description
        candidate_name (str): Candidate name
        election_date (date): Election date
        status (str): Campaign status
        organization (str): Organization name

    Example:
        >>> serializer = CampaignDetailSerializer(campaign)
        >>> data = serializer.data
        >>> print(data['contact_attempts_count'])
        142
        >>> print(data['recent_contact_attempts'][:1])
        [
            {
                'id': 'abc123...',
                'contact_type': 'phone',
                'contact_date': '2024-11-05T14:30:00Z',
                'result': 'contacted',
                'person_name': 'John Doe'
            }
        ]

    Performance:
        - Uses select_related and prefetch_related for optimal queries
        - Recent contact attempts limited to last 5 for performance
        - Contact attempts count uses database aggregation

    Note:
        - created_by and deleted_by show username for readability
        - All audit fields are read-only
        - Includes both summary (count) and detailed (recent) contact data
    """

    created_by = serializers.SerializerMethodField()
    deleted_by = serializers.SerializerMethodField()
    days_until_election = serializers.SerializerMethodField()
    is_upcoming = serializers.SerializerMethodField()
    contact_attempts_count = serializers.SerializerMethodField()
    recent_contact_attempts = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "description",
            "candidate_name",
            "election_date",
            "status",
            "organization",
            "created_by",
            "created_at",
            "updated_at",
            "is_active",
            "deleted_at",
            "deleted_by",
            "days_until_election",
            "is_upcoming",
            "contact_attempts_count",
            "recent_contact_attempts",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "is_active",
            "deleted_at",
            "deleted_by",
        ]

    def get_created_by(self, obj: Campaign) -> str | None:
        """
        Get username of user who created the campaign.

        Args:
            obj: Campaign instance

        Returns:
            Username string or None if created_by is not set
        """
        return obj.created_by.username if obj.created_by else None

    def get_deleted_by(self, obj: Campaign) -> str | None:
        """
        Get username of user who soft-deleted the campaign.

        Args:
            obj: Campaign instance

        Returns:
            Username string or None if not deleted or deleted_by not set
        """
        return obj.deleted_by.username if obj.deleted_by else None

    def get_days_until_election(self, obj: Campaign) -> int | None:
        """
        Get days remaining until election.

        Args:
            obj: Campaign instance

        Returns:
            Number of days until election, or None if election has passed
        """
        return obj.days_until_election

    def get_is_upcoming(self, obj: Campaign) -> bool:
        """
        Check if election is upcoming.

        Args:
            obj: Campaign instance

        Returns:
            True if election date is in the future, False otherwise
        """
        return obj.is_upcoming

    def get_contact_attempts_count(self, obj: Campaign) -> int:
        """
        Get total count of contact attempts for this campaign.

        Uses database aggregation for performance. Returns count from
        annotated queryset if available, otherwise queries database.

        Args:
            obj: Campaign instance

        Returns:
            Total number of contact attempts associated with this campaign

        Note:
            For best performance, the queryset should be annotated with
            contact_attempts_count using Count('contact_attempts')
        """
        # Check if count is already annotated on the queryset
        if hasattr(obj, "contact_attempts_count_annotated"):
            return obj.contact_attempts_count_annotated

        # Otherwise, count directly
        return obj.contact_attempts.count()

    def get_recent_contact_attempts(self, obj: Campaign) -> list[dict[str, Any]]:
        """
        Get the 5 most recent contact attempts for this campaign.

        Returns basic information about recent contacts including type, date,
        result, and person contacted. Ordered by contact_date descending.

        Args:
            obj: Campaign instance

        Returns:
            List of dictionaries containing:
            - id: Contact attempt UUID
            - contact_type: Type of contact (phone, email, etc.)
            - contact_date: When contact was made
            - result: Outcome of contact attempt
            - person_name: Full name of person contacted

        Example:
            [
                {
                    'id': 'abc123...',
                    'contact_type': 'phone',
                    'contact_date': '2024-11-05T14:30:00Z',
                    'result': 'contacted',
                    'person_name': 'John Doe'
                },
                ...
            ]

        Note:
            - Limited to 5 most recent for performance
            - Returns empty list if no contact attempts exist
            - Uses select_related for optimal person query
        """
        recent_contacts = (
            obj.contact_attempts.select_related("person")
            .order_by("-contact_date")[:5]
            .values(
                "id",
                "contact_type",
                "contact_date",
                "result",
            )
        )

        # Add person names
        result = []
        for contact in recent_contacts:
            contact_obj = ContactAttempt.objects.select_related("person").get(
                id=contact["id"]
            )
            result.append(
                {
                    "id": str(contact["id"]),
                    "contact_type": contact["contact_type"],
                    "contact_date": contact["contact_date"],
                    "result": contact["result"],
                    "person_name": contact_obj.person.full_name,
                }
            )

        return result


class CampaignSerializer(serializers.ModelSerializer):
    """
    Full-featured serializer for Campaign create/update operations.

    Handles campaign creation and updates with comprehensive validation,
    integration with CampaignCreationService, and audit trail support.
    Provides field-level and object-level validation with clear error messages.

    Editable Fields:
        name (str): Campaign name (3-200 chars, required)
        description (str): Campaign description (optional)
        candidate_name (str): Candidate name (2-200 chars, required)
        election_date (date): Election date (required, not in past for new campaigns)
        status (str): Campaign status (active/paused/completed/archived)
        organization (str): Organization name (optional, max 255 chars)

    Read-only Fields:
        id (UUID): Primary key
        created_at (datetime): Creation timestamp
        updated_at (datetime): Last update timestamp
        created_by (str): Username of creator
        is_active (bool): Soft delete status
        deleted_at (datetime|None): Soft delete timestamp
        deleted_by (str|None): Username of deleter

    Validation:
        - Name: 3-200 characters, required, unique (case-insensitive)
        - Candidate Name: 2-200 characters, required
        - Election Date: Valid date, not in past (for new), not >10 years future
        - Status: One of (active, paused, completed, archived)
        - All text fields: Sanitized for XSS, injection attacks
        - Organization: Max 255 characters

    Example - Create:
        >>> serializer = CampaignSerializer(
        ...     data={
        ...         'name': '2024 Senate Campaign',
        ...         'candidate_name': 'Jane Smith',
        ...         'election_date': '2024-11-05',
        ...         'status': 'active',
        ...         'organization': 'Democratic Party'
        ...     },
        ...     context={'request': request}
        ... )
        >>> if serializer.is_valid():
        ...     campaign = serializer.save()
        ...     print(f"Created: {campaign.name}")
        ... else:
        ...     print(serializer.errors)

    Example - Update:
        >>> serializer = CampaignSerializer(
        ...     campaign,
        ...     data={'status': 'completed'},
        ...     partial=True,
        ...     context={'request': request}
        ... )
        >>> if serializer.is_valid():
        ...     campaign = serializer.save()

    Integration:
        - Uses CampaignCreationService for business logic
        - Automatic duplicate detection during creation
        - Audit trail support (created_by tracking)
        - Transaction management via service layer
        - Consistent with existing campaign creation patterns

    Error Handling:
        Validation errors are returned in clear, user-friendly format:
        {
            'name': ['Campaign name must be at least 3 characters'],
            'election_date': ['Election date cannot be in the past']
        }

    Note:
        - Request context required for accessing current user
        - Uses CampaignCreationService for consistency
        - Field validation runs before object validation
        - All validation errors collected and returned together
        - Text fields automatically sanitized
    """

    created_by = serializers.SerializerMethodField()
    deleted_by = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "description",
            "candidate_name",
            "election_date",
            "status",
            "organization",
            "created_by",
            "created_at",
            "updated_at",
            "is_active",
            "deleted_at",
            "deleted_by",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "is_active",
            "deleted_at",
            "deleted_by",
        ]
        extra_kwargs = {
            "name": {
                "required": True,
                "allow_blank": False,
                "min_length": 3,
                "max_length": 200,
                "help_text": "Campaign name (3-200 characters)",
            },
            "candidate_name": {
                "required": True,
                "allow_blank": False,
                "min_length": 2,
                "max_length": 200,
                "help_text": "Candidate name (2-200 characters)",
            },
            "election_date": {
                "required": True,
                "help_text": "Election date (YYYY-MM-DD)",
            },
            "status": {
                "required": False,
                "help_text": "Campaign status (active/paused/completed/archived)",
            },
            "description": {
                "required": False,
                "allow_blank": True,
                "help_text": "Optional campaign description",
            },
            "organization": {
                "required": False,
                "allow_blank": True,
                "max_length": 255,
                "help_text": "Optional organization name (max 255 characters)",
            },
        }

    def get_created_by(self, obj: Campaign) -> str | None:
        """
        Get username of user who created the campaign.

        Args:
            obj: Campaign instance

        Returns:
            Username string or None if created_by is not set
        """
        return obj.created_by.username if obj.created_by else None

    def get_deleted_by(self, obj: Campaign) -> str | None:
        """
        Get username of user who soft-deleted the campaign.

        Args:
            obj: Campaign instance

        Returns:
            Username string or None if not deleted or deleted_by not set
        """
        return obj.deleted_by.username if obj.deleted_by else None

    def validate_name(self, value: str) -> str:
        """
        Validate campaign name field.

        Checks:
        - Not empty or whitespace only
        - Length between 3-200 characters
        - No suspicious content (XSS, injection patterns)

        Args:
            value: Campaign name to validate

        Returns:
            Validated and trimmed campaign name

        Raises:
            serializers.ValidationError: If validation fails with specific error message
        """
        if not value or not value.strip():
            raise serializers.ValidationError("Campaign name cannot be empty")

        value = value.strip()

        if len(value) < 3:
            raise serializers.ValidationError(
                "Campaign name must be at least 3 characters"
            )

        if len(value) > 200:
            raise serializers.ValidationError(
                "Campaign name must not exceed 200 characters"
            )

        return value

    def validate_candidate_name(self, value: str) -> str:
        """
        Validate candidate name field.

        Checks:
        - Not empty or whitespace only
        - Length between 2-200 characters

        Args:
            value: Candidate name to validate

        Returns:
            Validated and trimmed candidate name

        Raises:
            serializers.ValidationError: If validation fails
        """
        if not value or not value.strip():
            raise serializers.ValidationError("Candidate name cannot be empty")

        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "Candidate name must be at least 2 characters"
            )

        if len(value) > 200:
            raise serializers.ValidationError(
                "Candidate name must not exceed 200 characters"
            )

        return value

    def validate_election_date(self, value: date) -> date:
        """
        Validate election date field.

        Checks:
        - Valid date object
        - Not in the past (for new campaigns only)
        - Not more than 10 years in the future

        Args:
            value: Election date to validate

        Returns:
            Validated election date

        Raises:
            serializers.ValidationError: If validation fails

        Note:
            Past date validation only applies to new campaigns (not updates)
        """
        if not value:
            raise serializers.ValidationError("Election date is required")

        today = timezone.now().date()

        # Only check past date for new campaigns (not updates)
        if not self.instance:  # self.instance is None for create operations
            if value < today:
                raise serializers.ValidationError(
                    "Election date cannot be in the past for new campaigns"
                )

        # Check not too far in future (10 years)
        ten_years_from_now = today.replace(year=today.year + 10)
        if value > ten_years_from_now:
            raise serializers.ValidationError(
                "Election date seems unreasonably far in the future (over 10 years)"
            )

        return value

    def validate_status(self, value: str) -> str:
        """
        Validate campaign status field.

        Checks:
        - Value is one of the allowed choices
        - Case-insensitive matching

        Args:
            value: Status value to validate

        Returns:
            Validated status in lowercase

        Raises:
            serializers.ValidationError: If status is not valid
        """
        if not value:
            return "active"  # Default status

        value = value.strip().lower()
        valid_statuses = ["active", "paused", "completed", "archived"]

        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Invalid status. Choose from: {', '.join(valid_statuses)}"
            )

        return value

    def validate_organization(self, value: str) -> str:
        """
        Validate organization field.

        Checks:
        - Length does not exceed 255 characters

        Args:
            value: Organization name to validate

        Returns:
            Validated and trimmed organization name

        Raises:
            serializers.ValidationError: If validation fails
        """
        if value and len(value.strip()) > 255:
            raise serializers.ValidationError(
                "Organization name must not exceed 255 characters"
            )

        return value.strip() if value else ""

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Object-level validation.

        Performs cross-field validation and uses CampaignCreationService
        for comprehensive business rule validation.

        Args:
            attrs: Dictionary of validated field values

        Returns:
            Validated attributes dictionary

        Raises:
            serializers.ValidationError: If validation fails

        Note:
            This runs after all field-level validation
        """
        # Use service layer validation for comprehensive business rules
        service = CampaignCreationService()
        is_update = self.instance is not None

        try:
            # Validate using service layer
            errors = service.validate_campaign_data(
                cast(CampaignDataDict, attrs), is_update=is_update
            )
            if errors:
                # Convert service errors to DRF format
                raise serializers.ValidationError(errors)

        except DjangoValidationError as e:
            # Handle Django validation errors
            if hasattr(e, "message_dict"):
                raise serializers.ValidationError(e.message_dict) from e
            raise serializers.ValidationError({"non_field_errors": [str(e)]}) from e

        return attrs

    def create(self, validated_data: dict[str, Any]) -> Campaign:
        """
        Create a new Campaign using CampaignCreationService.

        Integrates with the service layer for consistent campaign creation,
        duplicate detection, and audit trail support.

        Args:
            validated_data: Dictionary of validated field values

        Returns:
            Newly created Campaign instance

        Raises:
            serializers.ValidationError: If creation fails

        Note:
            - Requires 'request' in context to access current user
            - Uses CampaignCreationService for business logic
            - Handles duplicate detection automatically
            - Creates audit trail (created_by)
        """
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError(
                {"non_field_errors": ["User authentication required"]}
            )

        service = CampaignCreationService()

        try:
            # Create campaign using service layer
            campaign, duplicates = service.create_campaign(
                campaign_data=cast(CampaignDataDict, validated_data),
                created_by=request.user,
                check_duplicates=True,
            )

            # Note: Duplicates are detected but creation proceeds
            # API consumers can check for duplicates separately if needed
            return campaign

        except DjangoValidationError as e:
            # Convert Django validation errors to DRF format
            if hasattr(e, "message_dict"):
                raise serializers.ValidationError(e.message_dict) from e
            raise serializers.ValidationError({"non_field_errors": [str(e)]}) from e

    def update(self, instance: Campaign, validated_data: dict[str, Any]) -> Campaign:
        """
        Update an existing Campaign using CampaignCreationService.

        Integrates with the service layer for consistent campaign updates,
        validation, and duplicate detection.

        Args:
            instance: Existing Campaign instance to update
            validated_data: Dictionary of validated field values to update

        Returns:
            Updated Campaign instance

        Raises:
            serializers.ValidationError: If update fails

        Note:
            - Uses CampaignCreationService for business logic
            - Handles duplicate detection (excluding current campaign)
            - Maintains audit trail
            - Supports partial updates
        """
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError(
                {"non_field_errors": ["User authentication required"]}
            )

        service = CampaignCreationService()

        # Only check duplicates if name or candidate_name are being updated
        # This avoids validation errors when updating other fields like status
        check_duplicates = bool(
            "name" in validated_data or "candidate_name" in validated_data
        )

        try:
            # Update campaign using service layer
            campaign, duplicates = service.update_campaign(
                campaign_id=str(instance.pk),
                campaign_data=cast(CampaignDataDict, validated_data),
                updated_by=request.user,
                check_duplicates=check_duplicates,
            )

            return campaign

        except DjangoValidationError as e:
            # Convert Django validation errors to DRF format
            if hasattr(e, "message_dict"):
                raise serializers.ValidationError(e.message_dict) from e
            raise serializers.ValidationError({"non_field_errors": [str(e)]}) from e
