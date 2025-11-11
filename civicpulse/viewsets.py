"""
Django REST Framework viewsets for CivicPulse Campaign API.

This module provides ViewSet implementations for Campaign model operations with:
- Full CRUD operations (Create, Read, Update, Delete)
- Different serializers for different actions (list, detail, create/update)
- Authentication and permission controls
- Filtering, searching, and ordering capabilities
- Custom actions (archive, activate, duplicate_check)
- Soft delete functionality
- Rate limiting for API endpoints
- Comprehensive error handling
- Type hints and documentation

ViewSets:
    CampaignViewSet: Complete API endpoint for Campaign operations

Example Usage:
    # Router configuration (in urls.py)
    from rest_framework.routers import DefaultRouter
    from civicpulse.viewsets import CampaignViewSet

    router = DefaultRouter()
    router.register(r'campaigns', CampaignViewSet, basename='campaign')
    urlpatterns += router.urls

    # Available endpoints:
    # GET    /campaigns/              - List all campaigns
    # POST   /campaigns/              - Create new campaign
    # GET    /campaigns/{id}/         - Get campaign detail
    # PUT    /campaigns/{id}/         - Update campaign (full)
    # PATCH  /campaigns/{id}/         - Update campaign (partial)
    # DELETE /campaigns/{id}/         - Soft delete campaign
    # PATCH  /campaigns/{id}/archive/ - Archive campaign
    # PATCH  /campaigns/{id}/activate/ - Activate campaign
    # POST   /campaigns/duplicate_check/ - Check for duplicates

Rate Limits:
    - list: 100 requests per hour
    - create: 20 requests per hour
    - update/partial_update: 50 requests per hour
    - destroy: 10 requests per hour

Authentication:
    - Session Authentication
    - Basic Authentication
    - All endpoints require IsAuthenticated permission

Filtering:
    - Search: name, candidate_name, description
    - Order by: name, election_date, created_at, status
    - Filter by: status, organization
"""

from typing import Any

from django.db.models import Prefetch, QuerySet
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from civicpulse.models import Campaign, ContactAttempt
from civicpulse.serializers import (
    CampaignDetailSerializer,
    CampaignListSerializer,
    CampaignSerializer,
)


class CampaignViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Campaign API operations with full CRUD support.

    Provides comprehensive Campaign management with different serializers
    for different actions, query optimization, filtering, and custom actions.

    Endpoints:
        GET    /campaigns/              - List all campaigns (paginated)
        POST   /campaigns/              - Create new campaign
        GET    /campaigns/{id}/         - Retrieve campaign details
        PUT    /campaigns/{id}/         - Full update of campaign
        PATCH  /campaigns/{id}/         - Partial update of campaign
        DELETE /campaigns/{id}/         - Soft delete campaign
        PATCH  /campaigns/{id}/archive/ - Archive campaign (custom action)
        PATCH  /campaigns/{id}/activate/ - Activate campaign (custom action)
        POST   /campaigns/duplicate_check/ - Check for duplicate campaigns

    Serializers:
        - list: CampaignListSerializer (lightweight, optimized for lists)
        - retrieve: CampaignDetailSerializer (comprehensive with relationships)
        - create/update/partial_update: CampaignSerializer (full validation)

    Query Optimization:
        - Uses select_related for created_by, deleted_by
        - Uses prefetch_related for contact_attempts
        - Optimizes queries based on action type

    Filtering:
        - Search: name, candidate_name, description (SearchFilter)
        - Ordering: name, election_date, created_at, status (OrderingFilter)
        - Filter: status, organization (query parameters)

    Permissions:
        - IsAuthenticated: All users must be logged in
        - Future: Can be extended with object-level permissions

    Rate Limiting:
        - list: 100 requests/hour
        - create: 20 requests/hour
        - update/partial_update: 50 requests/hour
        - destroy: 10 requests/hour

    Soft Delete:
        - destroy() performs soft delete (sets is_active=False)
        - Preserves audit trail (deleted_at, deleted_by)
        - Does not remove from database

    Example:
        # List campaigns with search and filtering
        GET /campaigns/?search=senate&status=active&ordering=-election_date

        # Create new campaign
        POST /campaigns/
        {
            "name": "2024 Senate Campaign",
            "candidate_name": "Jane Smith",
            "election_date": "2024-11-05",
            "status": "active",
            "organization": "Democratic Party"
        }

        # Archive a campaign
        PATCH /campaigns/{id}/archive/

        # Check for duplicates
        POST /campaigns/duplicate_check/
        {
            "name": "2024 Senate Campaign",
            "candidate_name": "Jane Smith",
            "election_date": "2024-11-05"
        }
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "candidate_name", "description"]
    ordering_fields = ["name", "election_date", "created_at", "status"]
    ordering = ["-created_at"]  # Default ordering

    def get_queryset(self) -> QuerySet[Campaign]:
        """
        Get optimized queryset for campaigns.

        Applies select_related and prefetch_related for performance optimization
        based on the action being performed. Only returns active (non-soft-deleted)
        campaigns by default.

        Returns:
            QuerySet[Campaign]: Optimized queryset with related objects pre-fetched

        Query Optimization:
            - select_related: created_by, deleted_by (one-to-one/foreign key)
            - prefetch_related: contact_attempts (reverse foreign key)

        Filtering:
            - Supports query parameters: status, organization
            - Only returns is_active=True campaigns by default

        Example:
            # Filter by status
            GET /campaigns/?status=active

            # Filter by organization
            GET /campaigns/?organization=Democratic%20Party

            # Combined filters
            GET /campaigns/?status=active&organization=DNC
        """
        queryset = Campaign.objects.select_related(
            "created_by",
            "deleted_by",
        ).prefetch_related(
            Prefetch(
                "contact_attempts",
                queryset=ContactAttempt.objects.select_related(
                    "person", "contacted_by"
                ),
            )
        )

        # Apply filters from query parameters
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        organization_filter = self.request.query_params.get("organization")
        if organization_filter:
            queryset = queryset.filter(organization__icontains=organization_filter)

        return queryset

    def get_serializer_class(self) -> type[Serializer]:
        """
        Get the appropriate serializer class based on the action.

        Different serializers are used for different operations:
        - list: Lightweight serializer for performance
        - retrieve: Detailed serializer with all relationships
        - create/update/partial_update: Full serializer with validation

        Returns:
            Type[Serializer]: Serializer class for the current action

        Serializer Selection:
            - CampaignListSerializer: list action (minimal fields, fast)
            - CampaignDetailSerializer: retrieve action (all fields, relationships)
            - CampaignSerializer: create/update actions (full validation)
        """
        if self.action == "list":
            return CampaignListSerializer
        elif self.action == "retrieve":
            return CampaignDetailSerializer
        return CampaignSerializer

    @method_decorator(ratelimit(key="user", rate="100/h", method="GET"))
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        List all campaigns with pagination, filtering, and search.

        Rate Limited: 100 requests per hour per user

        Query Parameters:
            - search: Search in name, candidate_name, description
            - ordering: Order by name, election_date, created_at, status
            - status: Filter by campaign status
            - organization: Filter by organization (case-insensitive contains)
            - page: Page number for pagination
            - page_size: Number of results per page

        Returns:
            Response: Paginated list of campaigns with metadata

        Response Format:
            {
                "count": 42,
                "next": "http://api.example.com/campaigns/?page=2",
                "previous": null,
                "results": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "2024 Senate Campaign",
                        "candidate_name": "Jane Smith",
                        "election_date": "2024-11-05",
                        "status": "active",
                        "days_until_election": 45,
                        "is_upcoming": true
                    },
                    ...
                ]
            }

        Example:
            GET /campaigns/?search=senate&status=active&ordering=-election_date
        """
        return super().list(request, *args, **kwargs)

    @method_decorator(ratelimit(key="user", rate="20/h", method="POST"))
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Create a new campaign.

        Rate Limited: 20 requests per hour per user

        Request Body:
            {
                "name": "Campaign name (required, 3-200 chars)",
                "candidate_name": "Candidate name (required, 2-200 chars)",
                "election_date": "YYYY-MM-DD (required, not in past)",
                "status": "active|paused|completed|archived (optional)",
                "organization": "Organization name (optional, max 255 chars)",
                "description": "Campaign description (optional)"
            }

        Returns:
            Response: Created campaign with status 201

        Response Format:
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "2024 Senate Campaign",
                "candidate_name": "Jane Smith",
                "election_date": "2024-11-05",
                "status": "active",
                "organization": "Democratic Party",
                "description": "Campaign for Senate seat",
                "created_by": "john_smith",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "is_active": true,
                "deleted_at": null,
                "deleted_by": null
            }

        Validation:
            - Name: 3-200 characters, required, unique (case-insensitive)
            - Candidate Name: 2-200 characters, required
            - Election Date: Valid date, not in past, not >10 years future
            - Status: One of (active, paused, completed, archived)
            - All text fields sanitized for XSS, injection attacks

        Errors:
            - 400: Validation error
            - 401: Authentication required
            - 429: Rate limit exceeded

        Example:
            POST /campaigns/
            {
                "name": "2024 Senate Campaign",
                "candidate_name": "Jane Smith",
                "election_date": "2024-11-05",
                "status": "active",
                "organization": "Democratic Party"
            }
        """
        return super().create(request, *args, **kwargs)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Retrieve detailed campaign information.

        Returns comprehensive campaign data including all fields,
        related contact attempts, and computed properties.

        Path Parameters:
            - id: Campaign UUID

        Returns:
            Response: Detailed campaign information

        Response Format:
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "2024 Senate Campaign",
                "description": "Campaign description",
                "candidate_name": "Jane Smith",
                "election_date": "2024-11-05",
                "status": "active",
                "organization": "Democratic Party",
                "created_by": "john_smith",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "is_active": true,
                "deleted_at": null,
                "deleted_by": null,
                "days_until_election": 45,
                "is_upcoming": true,
                "contact_attempts_count": 142,
                "recent_contact_attempts": [
                    {
                        "id": "abc123...",
                        "contact_type": "phone",
                        "contact_date": "2024-11-05T14:30:00Z",
                        "result": "contacted",
                        "person_name": "John Doe"
                    },
                    ...
                ]
            }

        Errors:
            - 401: Authentication required
            - 404: Campaign not found

        Example:
            GET /campaigns/123e4567-e89b-12d3-a456-426614174000/
        """
        return super().retrieve(request, *args, **kwargs)

    @method_decorator(ratelimit(key="user", rate="50/h", method=["PUT", "PATCH"]))
    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Full update of campaign (PUT).

        Rate Limited: 50 requests per hour per user (combined with partial_update)

        Path Parameters:
            - id: Campaign UUID

        Request Body:
            All fields required (full update):
            {
                "name": "Updated campaign name",
                "candidate_name": "Updated candidate name",
                "election_date": "2024-11-05",
                "status": "active",
                "organization": "Updated organization",
                "description": "Updated description"
            }

        Returns:
            Response: Updated campaign with status 200

        Validation:
            - All fields validated as in create
            - Election date can be in past for existing campaigns
            - Name uniqueness checked (excluding current campaign)

        Errors:
            - 400: Validation error
            - 401: Authentication required
            - 404: Campaign not found
            - 429: Rate limit exceeded

        Example:
            PUT /campaigns/123e4567-e89b-12d3-a456-426614174000/
            {
                "name": "Updated 2024 Senate Campaign",
                "candidate_name": "Jane Smith",
                "election_date": "2024-11-05",
                "status": "active",
                "organization": "Democratic Party",
                "description": "Updated campaign description"
            }
        """
        return super().update(request, *args, **kwargs)

    @method_decorator(ratelimit(key="user", rate="50/h", method=["PUT", "PATCH"]))
    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Partial update of campaign (PATCH).

        Rate Limited: 50 requests per hour per user (combined with update)

        Path Parameters:
            - id: Campaign UUID

        Request Body:
            Only fields to update (partial update):
            {
                "status": "completed"
            }

        Returns:
            Response: Updated campaign with status 200

        Common Updates:
            - Status change: {"status": "completed"}
            - Organization update: {"organization": "New org"}
            - Description update: {"description": "New description"}

        Validation:
            - Only provided fields are validated and updated
            - Omitted fields retain their current values

        Errors:
            - 400: Validation error
            - 401: Authentication required
            - 404: Campaign not found
            - 429: Rate limit exceeded

        Example:
            PATCH /campaigns/123e4567-e89b-12d3-a456-426614174000/
            {
                "status": "completed"
            }
        """
        return super().partial_update(request, *args, **kwargs)

    @method_decorator(ratelimit(key="user", rate="10/h", method="DELETE"))
    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Soft delete a campaign.

        Rate Limited: 10 requests per hour per user

        Performs soft delete by setting:
        - is_active = False
        - deleted_at = current timestamp
        - deleted_by = current user

        Campaign is not removed from database and can be restored if needed.

        Path Parameters:
            - id: Campaign UUID

        Returns:
            Response: Empty response with status 204 (No Content)

        Soft Delete Benefits:
            - Preserves historical data and relationships
            - Maintains referential integrity
            - Can be restored if deleted by mistake
            - Audit trail of who deleted and when

        Errors:
            - 401: Authentication required
            - 404: Campaign not found
            - 429: Rate limit exceeded

        Note:
            - Soft-deleted campaigns are excluded from default queries
            - Use Campaign.objects.all_with_deleted() to see deleted campaigns
            - Contact attempts remain linked to soft-deleted campaigns

        Example:
            DELETE /campaigns/123e4567-e89b-12d3-a456-426614174000/
        """
        instance = self.get_object()
        instance.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer: Serializer) -> None:
        """
        Ensure created_by is set when creating a campaign.

        Called by create() to save the instance. Sets the created_by
        field to the current user before saving.

        Args:
            serializer: Validated serializer with campaign data

        Note:
            This is called automatically by DRF create() method.
            The actual creation logic is in CampaignSerializer.create()
            which uses CampaignCreationService.
        """
        # The serializer's create() method handles created_by via service layer
        serializer.save()

    def perform_update(self, serializer: Serializer) -> None:
        """
        Track updates to campaigns.

        Called by update() and partial_update() to save the instance.
        The updated_at field is automatically updated by Django.

        Args:
            serializer: Validated serializer with campaign data

        Note:
            This is called automatically by DRF update/partial_update methods.
            The actual update logic is in CampaignSerializer.update()
            which uses CampaignCreationService.
            Future: Could track updated_by if added to model.
        """
        serializer.save()

    @action(detail=True, methods=["patch"], url_path="archive")
    def archive(self, request: Request, pk: str | None = None) -> Response:
        """
        Archive a campaign (custom action).

        Sets campaign status to 'archived'. Archived campaigns are
        completed campaigns that are kept for historical reference.

        Path Parameters:
            - id: Campaign UUID

        Returns:
            Response: Updated campaign with status 200

        Response Format:
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "2024 Senate Campaign",
                "status": "archived",
                ...
            }

        Use Cases:
            - Archive completed campaigns
            - Keep historical record without cluttering active campaigns
            - Maintain audit trail of past campaigns

        Errors:
            - 401: Authentication required
            - 404: Campaign not found

        Example:
            PATCH /campaigns/123e4567-e89b-12d3-a456-426614174000/archive/
        """
        campaign = self.get_object()
        campaign.status = "archived"
        campaign.save(update_fields=["status", "updated_at"])
        serializer = self.get_serializer(campaign)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="activate")
    def activate(self, request: Request, pk: str | None = None) -> Response:
        """
        Activate a campaign (custom action).

        Sets campaign status to 'active'. Used to reactivate
        paused or archived campaigns.

        Path Parameters:
            - id: Campaign UUID

        Returns:
            Response: Updated campaign with status 200

        Response Format:
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "2024 Senate Campaign",
                "status": "active",
                ...
            }

        Use Cases:
            - Reactivate paused campaigns
            - Resume archived campaigns
            - Quick status change without full update

        Errors:
            - 401: Authentication required
            - 404: Campaign not found

        Example:
            PATCH /campaigns/123e4567-e89b-12d3-a456-426614174000/activate/
        """
        campaign = self.get_object()
        campaign.status = "active"
        campaign.save(update_fields=["status", "updated_at"])
        serializer = self.get_serializer(campaign)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="duplicate_check")
    def duplicate_check(self, request: Request) -> Response:
        """
        Check for potential duplicate campaigns (custom action).

        Performs duplicate detection based on:
        - Campaign name (case-insensitive)
        - Candidate name and election date combination
        - Similar campaigns within same organization

        This is a read-only check that does not create a campaign.

        Request Body:
            {
                "name": "2024 Senate Campaign",
                "candidate_name": "Jane Smith",
                "election_date": "2024-11-05",
                "organization": "Democratic Party"  // optional
            }

        Returns:
            Response: List of potential duplicates with status 200

        Response Format:
            {
                "has_duplicates": true,
                "duplicate_count": 2,
                "duplicates": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "2024 Senate Campaign",
                        "candidate_name": "Jane Smith",
                        "election_date": "2024-11-05",
                        "status": "active",
                        "organization": "Democratic Party",
                        "similarity_reason": "exact_name_match"
                    },
                    {
                        "id": "456e7890-e89b-12d3-a456-426614174001",
                        "name": "Senate Campaign 2024",
                        "candidate_name": "Jane Smith",
                        "election_date": "2024-11-05",
                        "status": "active",
                        "organization": "Democratic Party",
                        "similarity_reason": "same_candidate_and_date"
                    }
                ]
            }

        Duplicate Detection Rules:
            - Exact name match (case-insensitive)
            - Same candidate + same election date
            - Similar name in same organization

        Use Cases:
            - Check before creating new campaign
            - Prevent duplicate campaign entries
            - Find related campaigns

        Errors:
            - 400: Invalid request data
            - 401: Authentication required

        Example:
            POST /campaigns/duplicate_check/
            {
                "name": "2024 Senate Campaign",
                "candidate_name": "Jane Smith",
                "election_date": "2024-11-05"
            }
        """
        # Validate required fields
        name = request.data.get("name")
        candidate_name = request.data.get("candidate_name")
        election_date = request.data.get("election_date")

        if not all([name, candidate_name, election_date]):
            return Response(
                {
                    "error": "name, candidate_name, and election_date are required",
                    "has_duplicates": False,
                    "duplicate_count": 0,
                    "duplicates": [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find potential duplicates
        duplicates = []
        queryset = Campaign.objects.all()

        # Check exact name match (case-insensitive)
        exact_name_matches = queryset.filter(name__iexact=name.strip())
        for campaign in exact_name_matches:
            duplicates.append(
                {
                    "id": str(campaign.id),
                    "name": campaign.name,
                    "candidate_name": campaign.candidate_name,
                    "election_date": str(campaign.election_date),
                    "status": campaign.status,
                    "organization": campaign.organization,
                    "similarity_reason": "exact_name_match",
                }
            )

        # Check same candidate + same election date
        same_candidate_date = queryset.filter(
            candidate_name__iexact=candidate_name.strip(),
            election_date=election_date,
        ).exclude(id__in=[d["id"] for d in duplicates])

        for campaign in same_candidate_date:
            duplicates.append(
                {
                    "id": str(campaign.id),
                    "name": campaign.name,
                    "candidate_name": campaign.candidate_name,
                    "election_date": str(campaign.election_date),
                    "status": campaign.status,
                    "organization": campaign.organization,
                    "similarity_reason": "same_candidate_and_date",
                }
            )

        # If organization provided, check similar names in same org
        organization = request.data.get("organization")
        if organization:
            name_parts = name.strip().split()
            if len(name_parts) >= 2:
                # Search for campaigns with similar names in same organization
                similar_in_org = queryset.filter(
                    organization__iexact=organization.strip()
                ).exclude(id__in=[d["id"] for d in duplicates])

                # Check if campaign names contain major keywords
                for campaign in similar_in_org:
                    campaign_parts = campaign.name.lower().split()
                    matching_parts = sum(
                        1 for part in name_parts if part.lower() in campaign_parts
                    )
                    # If more than half the words match, consider it similar
                    if matching_parts >= len(name_parts) / 2:
                        duplicates.append(
                            {
                                "id": str(campaign.id),
                                "name": campaign.name,
                                "candidate_name": campaign.candidate_name,
                                "election_date": str(campaign.election_date),
                                "status": campaign.status,
                                "organization": campaign.organization,
                                "similarity_reason": "similar_name_same_organization",
                            }
                        )

        return Response(
            {
                "has_duplicates": len(duplicates) > 0,
                "duplicate_count": len(duplicates),
                "duplicates": duplicates,
            }
        )
