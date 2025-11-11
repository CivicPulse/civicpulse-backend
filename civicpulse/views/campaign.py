"""
Campaign views for CivicPulse application.

This module provides views for creating, viewing, and managing Campaign records:
- CampaignListView: List campaigns with filtering, search, and pagination
- CampaignCreateView: Create new campaigns with duplicate detection and rate limiting
- CampaignDetailView: View campaign details
- CampaignUpdateView: Update campaign information with validation
- CampaignDeleteView: Soft delete campaigns (set is_active=False)

Features:
- Rate limiting to prevent abuse
- Duplicate detection with user confirmation flow
- Comprehensive error handling and user feedback
- Integration with CampaignCreationService for business logic
- Secure, authenticated access only
- Search and filtering capabilities
- Soft delete functionality
"""

from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q, QuerySet
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, FormView, ListView, UpdateView, View
from django_ratelimit.decorators import ratelimit
from loguru import logger

from civicpulse.forms import CampaignForm
from civicpulse.models import Campaign
from civicpulse.services.campaign_service import CampaignCreationService

if TYPE_CHECKING:
    from civicpulse.models import User
else:
    User = get_user_model()


@method_decorator(login_required, name="dispatch")
class CampaignListView(LoginRequiredMixin, ListView):
    """
    View for displaying a paginated list of campaigns with search and filtering.

    This view provides a comprehensive campaign listing with:
    1. Pagination (20 campaigns per page)
    2. Search by campaign name and candidate name
    3. Filtering by status and organization
    4. Optimized queryset with select_related for performance
    5. Ordering by creation date (newest first)

    Features:
    - Authenticated access only
    - Search functionality for campaign and candidate names
    - Filter by campaign status (active, paused, completed, archived)
    - Filter by organization
    - Efficient database queries with select_related
    - Context includes search query and filter values

    Attributes:
        model: Campaign model class
        template_name: Path to the list template
        context_object_name: Name of the campaign list in template context
        paginate_by: Number of campaigns per page

    Example:
        In urls.py:
        >>> path('campaigns/', CampaignListView.as_view(), name='campaign-list')

        In template:
        >>> {% for campaign in campaigns %}
        ...   <h3>{{ campaign.name }}</h3>
        ...   <p>Candidate: {{ campaign.candidate_name }}</p>
        ...   <p>Election: {{ campaign.election_date }}</p>
        ... {% endfor %}

    Query Parameters:
        - q: Search query for campaign/candidate name
        - status: Filter by campaign status
        - organization: Filter by organization name

    Note:
        - Requires authenticated user (@login_required)
        - Only shows active campaigns (is_active=True)
        - Uses select_related('created_by') for performance
        - Orders by -created_at (newest first)
    """

    model = Campaign
    template_name = "civicpulse/campaign/list.html"
    context_object_name = "campaigns"
    paginate_by = 20

    def get_queryset(self) -> QuerySet[Campaign]:
        """
        Return filtered and optimized queryset of active campaigns.

        Applies:
        1. Filter to only active campaigns (is_active=True)
        2. Search by campaign name or candidate name (case-insensitive)
        3. Filter by status if provided
        4. Filter by organization if provided
        5. Optimize with select_related for created_by user
        6. Order by creation date (newest first)

        Returns:
            Filtered and optimized QuerySet of Campaign objects

        Query Parameters:
            - q: Search term for campaign/candidate name
            - status: Campaign status to filter by
            - organization: Organization name to filter by
        """
        # Start with active campaigns only
        queryset = Campaign.objects.filter(is_active=True)

        # Apply search filter if query parameter is present
        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            # Search in both campaign name and candidate name (case-insensitive)
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(candidate_name__icontains=search_query)
            )
            logger.debug(f"Applied search filter: {search_query}")

        # Apply status filter if present
        status_filter = self.request.GET.get("status", "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            logger.debug(f"Applied status filter: {status_filter}")

        # Apply organization filter if present
        organization_filter = self.request.GET.get("organization", "").strip()
        if organization_filter:
            queryset = queryset.filter(organization__icontains=organization_filter)
            logger.debug(f"Applied organization filter: {organization_filter}")

        # Optimize query with select_related for created_by user
        queryset = queryset.select_related("created_by")

        # Order by creation date (newest first)
        queryset = queryset.order_by("-created_at")

        logger.info(
            f"Campaign list query returned {queryset.count()} results "
            f"for user {self.request.user}"
        )

        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Add additional context data to template.

        Args:
            **kwargs: Additional context from parent class

        Returns:
            Context dictionary with additional keys:
                - page_title: Title for the page
                - search_query: Current search query from URL parameters
                - status_filter: Current status filter value
                - organization_filter: Current organization filter value
                - status_choices: Available status options for filtering
        """
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Campaigns"

        # Add search query to context for form population
        context["search_query"] = self.request.GET.get("q", "")

        # Add filter values to context
        context["status_filter"] = self.request.GET.get("status", "")
        context["organization_filter"] = self.request.GET.get("organization", "")

        # Add status choices for filter dropdown
        context["status_choices"] = Campaign.STATUS_CHOICES

        return context


@method_decorator(ratelimit(key="ip", rate="20/h", method="POST"), name="post")
@method_decorator(login_required, name="dispatch")
class CampaignCreateView(LoginRequiredMixin, FormView):
    """
    View for creating new Campaign records with duplicate detection.

    This view handles the complete campaign creation workflow including:
    1. Form validation using CampaignForm
    2. Duplicate detection using CampaignCreationService
    3. User confirmation if duplicates are found
    4. Campaign creation via CampaignCreationService
    5. Success/error feedback to user

    Features:
    - Rate limiting: 20 requests per hour per IP address
    - Duplicate warning: Shows potential duplicates before creation
    - User confirmation: Allows user to proceed despite duplicates
    - Audit trail: Records created_by user
    - Error handling: Graceful handling of validation and integrity errors

    Attributes:
        template_name: Path to the creation form template
        form_class: CampaignForm for data validation
        success_url: URL pattern name for redirect after successful creation

    Example:
        In urls.py:
        >>> path(
        ...     'campaigns/create/',
        ...     CampaignCreateView.as_view(),
        ...     name='campaign-create'
        ... )

        In template:
        >>> <form method="post">
        ...   {% csrf_token %}
        ...   {{ form.as_p }}
        ...   <button type="submit">Create Campaign</button>
        ... </form>

    Note:
        - Requires authenticated user (@login_required)
        - Rate limited to prevent abuse (20 POST requests per hour)
        - Uses two-step process for duplicate handling:
          1. First submission: Show duplicates if found
          2. Second submission: Create despite duplicates if confirmed
    """

    template_name = "civicpulse/campaign/create.html"
    form_class = CampaignForm

    def get_success_url(self) -> str:
        """
        Return URL to redirect to after successful campaign creation.

        Returns:
            URL string pointing to the campaign detail page
        """
        # Will be set in form_valid() after campaign is created
        return reverse("civicpulse:campaign_detail", kwargs={"pk": self.campaign.pk})

    def form_valid(self, form: CampaignForm) -> HttpResponse:
        """
        Process valid form submission with duplicate detection flow.

        This method implements a two-step process:
        1. First submission: Check for duplicates and show warning
        2. Second submission (with confirm_duplicates): Create campaign

        Workflow:
        1. Check if user has confirmed duplicates
           (form data contains confirm_duplicates)
        2. If not confirmed and duplicates exist:
           - Add warning message
           - Re-render form with duplicate information
        3. If confirmed or no duplicates:
           - Create campaign via CampaignCreationService
           - Set created_by to current user
           - Add success message
           - Redirect to campaign detail page

        Args:
            form: Validated CampaignForm instance with cleaned data

        Returns:
            HttpResponse: Either redirect to success URL or re-rendered form
                with duplicate warnings

        Raises:
            ValidationError: Re-raised from CampaignCreationService if validation fails
            IntegrityError: Re-raised if database constraints are violated

        Example:
            First submission (duplicates found):
            >>> # User submits form
            >>> # Form is valid, but duplicates are found
            >>> # form_valid() adds warning message and re-renders form
            >>> # Template shows: "Found 2 potential duplicates. Review and confirm."

            Second submission (user confirms):
            >>> # User checks "confirm_duplicates" and submits
            >>> # form_valid() creates campaign and redirects
            >>> # Success message: "Campaign 'Vote for John Doe' created successfully"
        """
        logger.info(f"Processing campaign creation form from user {self.request.user}")

        # Check if user has confirmed despite duplicates
        confirm_duplicates = self.request.POST.get("confirm_duplicates") == "on"

        # If duplicates were found and user hasn't confirmed
        if form.duplicates and not confirm_duplicates:
            logger.warning(
                f"Found {len(form.duplicates)} potential duplicates, "
                f"requesting user confirmation"
            )

            # Add warning message
            duplicate_names = ", ".join(
                [
                    (
                        f"{c.name} (Election: {c.election_date}, "
                        f"Candidate: {c.candidate_name})"
                    )
                    for c in form.duplicates
                ]
            )
            messages.warning(
                self.request,
                f"Found {len(form.duplicates)} potential duplicate(s): "
                f"{duplicate_names}. "
                f"Please review and confirm if you want to create this campaign "
                f"anyway.",
            )

            # Re-render form with duplicate information in context
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    duplicates=form.duplicates,
                    show_duplicate_warning=True,
                )
            )

        # User confirmed or no duplicates found - proceed with creation
        try:
            from typing import cast

            from civicpulse.services.campaign_service import CampaignDataDict

            service = CampaignCreationService()

            # Create campaign via service (handles all business logic)
            campaign, duplicates = service.create_campaign(
                campaign_data=cast(CampaignDataDict, form.cleaned_data),
                created_by=cast(User, self.request.user),
                check_duplicates=False,  # Already checked in form.clean()
            )

            # Store campaign for get_success_url()
            self.campaign = campaign

            logger.info(
                f"Successfully created campaign: {campaign.pk} - {campaign.name} "
                f"by user {self.request.user}"
            )

            # Add success message
            messages.success(
                self.request,
                f"Campaign '{campaign.name}' created successfully. "
                f"You can now view and edit its information.",
            )

            # Redirect to campaign detail page
            return super().form_valid(form)

        except ValidationError as e:
            logger.error(f"Validation error creating campaign: {e}")

            # Add field-specific errors to form
            if hasattr(e, "message_dict"):
                for field, errors in e.message_dict.items():
                    for error in errors:
                        if field == "__all__":
                            form.add_error(None, error)
                        else:
                            form.add_error(field, error)
            else:
                form.add_error(None, str(e))

            # Re-render form with errors
            return self.form_invalid(form)

        except IntegrityError as e:
            logger.error(f"Database integrity error creating campaign: {e}")

            # Add user-friendly error message
            messages.error(
                self.request,
                "Unable to create campaign due to a database constraint. "
                "This campaign may already exist with the same name.",
            )

            form.add_error(
                None,
                "A campaign with this name already exists in the system.",
            )

            return self.form_invalid(form)

        except Exception as e:
            logger.exception(f"Unexpected error creating campaign: {e}")

            # Add generic error message
            messages.error(
                self.request,
                "An unexpected error occurred while creating the campaign. "
                "Please try again or contact support if the problem persists.",
            )

            form.add_error(
                None,
                "An unexpected error occurred. Please try again or contact support.",
            )

            return self.form_invalid(form)

    def form_invalid(self, form: CampaignForm) -> HttpResponse:
        """
        Handle invalid form submission.

        Adds error message and logs validation errors for debugging.

        Args:
            form: Invalid CampaignForm instance with errors

        Returns:
            HttpResponse: Re-rendered form with error messages
        """
        logger.warning(f"Campaign creation form invalid: {form.errors}")

        messages.error(
            self.request,
            "Please correct the errors below and try again. "
            "All required fields must be filled out correctly.",
        )

        return super().form_invalid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Add additional context data to template.

        Args:
            **kwargs: Additional context from parent class

        Returns:
            Context dictionary with additional keys:
                - page_title: Title for the page
                - submit_button_text: Text for submit button
                - duplicates: List of duplicate campaigns (if any)
                - show_duplicate_warning: Boolean flag for duplicate warning display
        """
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create New Campaign"
        context["submit_button_text"] = "Create Campaign"

        # Add duplicate information if present
        if "duplicates" in kwargs:
            context["duplicates"] = kwargs["duplicates"]
        if "show_duplicate_warning" in kwargs:
            context["show_duplicate_warning"] = kwargs["show_duplicate_warning"]

        return context


@method_decorator(login_required, name="dispatch")
class CampaignDetailView(LoginRequiredMixin, DetailView):
    """
    View for displaying Campaign details.

    This view shows comprehensive information about a specific Campaign record,
    including:
    - Campaign information (name, candidate, election date, status)
    - Description and organization details
    - Election countdown (days until election, is_upcoming)
    - Contact attempts related to this campaign (prefetched)
    - Audit information (created_by, created_at, updated_at)

    Features:
    - Authenticated access only
    - Automatic 404 for non-existent or soft-deleted campaigns
    - Context includes campaign object and related contact attempts
    - Displays election countdown information

    Attributes:
        model: Campaign model class
        template_name: Path to the detail template
        context_object_name: Name of the campaign object in template context

    Example:
        In urls.py:
        >>> path(
        ...     'campaigns/<uuid:pk>/',
        ...     CampaignDetailView.as_view(),
        ...     name='campaign-detail'
        ... )

        In template:
        >>> <h1>{{ campaign.name }}</h1>
        >>> <p>Candidate: {{ campaign.candidate_name }}</p>
        >>> <p>Election Date: {{ campaign.election_date }}</p>
        >>> <p>Status: {{ campaign.get_status_display }}</p>
        >>> {% if campaign.is_upcoming %}
        ...   <p>Days until election: {{ campaign.days_until_election }}</p>
        ... {% endif %}

    Note:
        - Requires authenticated user (@login_required)
        - Uses UUID primary key (pk) in URL
        - Automatically filters out soft-deleted campaigns (is_active=True)
        - Returns 404 if campaign doesn't exist or is deleted
        - Prefetches related contact_attempts for performance
    """

    model = Campaign
    template_name = "civicpulse/campaign/detail.html"
    context_object_name = "campaign"

    def get_queryset(self) -> QuerySet[Campaign]:
        """
        Filter queryset to only return active campaigns with optimized queries.

        Returns:
            QuerySet of Campaign objects where is_active=True,
            with prefetch_related for contact_attempts

        Note:
            This ensures soft-deleted campaigns (is_active=False) return 404
        """
        return Campaign.objects.filter(is_active=True).prefetch_related(
            "contact_attempts"
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Add additional context data to template.

        Args:
            **kwargs: Additional context from parent class

        Returns:
            Context dictionary with additional keys:
                - page_title: Title for the page (includes campaign name)
                - is_upcoming: Boolean indicating if election is in the future
                - days_until_election: Number of days until election (if upcoming)
        """
        context = super().get_context_data(**kwargs)
        campaign = self.get_object()
        context["page_title"] = f"Campaign: {campaign.name}"

        # Add election timing information
        context["is_upcoming"] = campaign.is_upcoming
        context["days_until_election"] = campaign.days_until_election

        logger.info(
            f"User {self.request.user} viewed campaign: {campaign.pk} - {campaign.name}"
        )

        return context


@method_decorator(ratelimit(key="ip", rate="50/h", method="POST"), name="post")
@method_decorator(login_required, name="dispatch")
class CampaignUpdateView(LoginRequiredMixin, UpdateView):
    """
    View for updating Campaign records.

    This view handles campaign updates with:
    1. Form validation using CampaignForm
    2. Update via CampaignCreationService for business logic
    3. Validation and error handling
    4. Success feedback to user

    Features:
    - Rate limiting: 50 requests per hour per IP address
    - Service layer integration for updates
    - Comprehensive error handling
    - Audit trail (updated_at automatic)
    - Success/error messages

    Attributes:
        model: Campaign model class
        form_class: CampaignForm for data validation
        template_name: Path to the edit form template
        context_object_name: Name of the campaign object in template context

    Example:
        In urls.py:
        >>> path(
        ...     'campaigns/<uuid:pk>/edit/',
        ...     CampaignUpdateView.as_view(),
        ...     name='campaign-edit'
        ... )

        In template:
        >>> <form method="post">
        ...   {% csrf_token %}
        ...   {{ form.as_p }}
        ...   <button type="submit">Update Campaign</button>
        ... </form>

    Note:
        - Requires authenticated user (@login_required)
        - Rate limited to prevent abuse (50 POST requests per hour)
        - Uses CampaignCreationService.update_campaign() for updates
        - Only updates active campaigns (is_active=True)
        - Redirects to campaign detail page on success
    """

    model = Campaign
    form_class = CampaignForm
    template_name = "civicpulse/campaign/edit.html"
    context_object_name = "campaign"

    def get_queryset(self) -> QuerySet[Campaign]:
        """
        Filter queryset to only return active campaigns.

        Returns:
            QuerySet of Campaign objects where is_active=True

        Note:
            This ensures soft-deleted campaigns cannot be edited
        """
        return Campaign.objects.filter(is_active=True)

    def get_success_url(self) -> str:
        """
        Return URL to redirect to after successful campaign update.

        Returns:
            URL string pointing to the campaign detail page
        """
        return reverse("civicpulse:campaign_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form: CampaignForm) -> HttpResponse:
        """
        Process valid form submission using CampaignCreationService.

        Args:
            form: Validated CampaignForm instance with cleaned data

        Returns:
            HttpResponse: Redirect to campaign detail page on success

        Raises:
            ValidationError: If service layer validation fails
        """
        logger.info(
            f"Processing campaign update for {self.object.pk} "
            f"by user {self.request.user}"
        )

        try:
            from typing import cast

            from civicpulse.services.campaign_service import CampaignDataDict

            service = CampaignCreationService()

            # Update campaign via service (handles all business logic)
            campaign, duplicates = service.update_campaign(
                campaign_id=str(self.object.pk),
                campaign_data=cast(CampaignDataDict, form.cleaned_data),
                updated_by=cast(User, self.request.user),
                check_duplicates=False,  # Skip duplicate check for updates
            )

            logger.info(
                f"Successfully updated campaign: {campaign.pk} - {campaign.name} "
                f"by user {self.request.user}"
            )

            # Add success message
            messages.success(
                self.request,
                f"Campaign '{campaign.name}' updated successfully.",
            )

            # Redirect to campaign detail page
            return super().form_valid(form)

        except ValidationError as e:
            logger.error(f"Validation error updating campaign: {e}")

            # Add field-specific errors to form
            if hasattr(e, "message_dict"):
                for field, errors in e.message_dict.items():
                    for error in errors:
                        if field == "__all__":
                            form.add_error(None, error)
                        else:
                            form.add_error(field, error)
            else:
                form.add_error(None, str(e))

            return self.form_invalid(form)

        except Exception as e:
            logger.exception(f"Unexpected error updating campaign: {e}")

            messages.error(
                self.request,
                "An unexpected error occurred while updating the campaign. "
                "Please try again or contact support.",
            )

            form.add_error(None, "An unexpected error occurred. Please try again.")

            return self.form_invalid(form)

    def form_invalid(self, form: CampaignForm) -> HttpResponse:
        """
        Handle invalid form submission.

        Args:
            form: Invalid CampaignForm instance with errors

        Returns:
            HttpResponse: Re-rendered form with error messages
        """
        logger.warning(f"Campaign update form invalid: {form.errors}")

        messages.error(
            self.request,
            "Please correct the errors below and try again.",
        )

        return super().form_invalid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Add additional context data to template.

        Args:
            **kwargs: Additional context from parent class

        Returns:
            Context dictionary with additional keys:
                - page_title: Title for the page
                - submit_button_text: Text for submit button
        """
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Campaign: {self.object.name}"
        context["submit_button_text"] = "Update Campaign"

        return context


@method_decorator(ratelimit(key="ip", rate="10/h", method="POST"), name="post")
@method_decorator(login_required, name="dispatch")
class CampaignDeleteView(LoginRequiredMixin, View):
    """
    View for soft-deleting Campaign records.

    This view implements soft delete functionality (setting is_active=False)
    rather than actually deleting the campaign from the database. This:
    1. Preserves audit trail and historical data
    2. Allows for potential restoration
    3. Maintains referential integrity
    4. Keeps related contact attempts and other data

    The soft delete process:
    1. Sets is_active = False
    2. Sets deleted_at = current timestamp
    3. Sets deleted_by = current user
    4. Leaves all other data intact

    Features:
    - Rate limiting: 10 requests per hour per IP address
    - Soft delete (preserves data)
    - Audit trail (records who deleted and when)
    - Confirmation required (via template)
    - Success/error messages

    Attributes:
        template_name: Path to the confirmation template

    Example:
        In urls.py:
        >>> path(
        ...     'campaigns/<uuid:pk>/delete/',
        ...     CampaignDeleteView.as_view(),
        ...     name='campaign-delete'
        ... )

        In confirmation template:
        >>> <form method="post">
        ...   {% csrf_token %}
        ...   <p>Are you sure you want to delete {{ campaign.name }}?</p>
        ...   <button type="submit">Confirm Delete</button>
        ... </form>

    HTTP Methods:
        GET: Display confirmation page
        POST: Perform soft delete operation

    Note:
        - Requires authenticated user (@login_required)
        - Rate limited to prevent abuse (10 POST requests per hour)
        - Soft deletes only (is_active=False, not actual deletion)
        - Records deleted_by and deleted_at for audit trail
        - Redirects to campaign list page on success
        - Cannot delete already-deleted campaigns (404)
    """

    template_name = "civicpulse/campaign/confirm_delete.html"

    def get(self, request, pk: str) -> HttpResponse:
        """
        Display confirmation page for campaign deletion.

        Args:
            request: HttpRequest object
            pk: UUID of the campaign to delete

        Returns:
            HttpResponse: Rendered confirmation template with campaign context

        Raises:
            Http404: If campaign doesn't exist or is already deleted
        """
        from django.shortcuts import get_object_or_404, render

        # Get the campaign or 404 if not found or already deleted
        campaign = get_object_or_404(Campaign, pk=pk, is_active=True)

        logger.info(
            f"User {request.user} requested confirmation to delete campaign: "
            f"{campaign.pk}"
        )

        context = {
            "campaign": campaign,
            "page_title": f"Delete Campaign: {campaign.name}",
        }

        return render(request, self.template_name, context)

    def post(self, request, pk: str) -> HttpResponse:
        """
        Perform soft delete operation on the campaign.

        This method:
        1. Retrieves the campaign
        2. Sets is_active = False
        3. Sets deleted_at = now()
        4. Sets deleted_by = current user
        5. Saves the changes
        6. Adds success message
        7. Redirects to campaign list

        Args:
            request: HttpRequest object
            pk: UUID of the campaign to delete

        Returns:
            HttpResponse: Redirect to campaign list page on success

        Raises:
            Http404: If campaign doesn't exist or is already deleted
        """
        from django.shortcuts import get_object_or_404, redirect

        # Get the campaign or 404 if not found or already deleted
        campaign = get_object_or_404(Campaign, pk=pk, is_active=True)

        campaign_name = campaign.name  # Store name before deletion

        logger.info(
            f"User {request.user} attempting to soft delete campaign: "
            f"{campaign.pk} - {campaign_name}"
        )

        try:
            # Perform soft delete
            campaign.is_active = False
            campaign.deleted_at = timezone.now()
            campaign.deleted_by = request.user
            campaign.save(update_fields=["is_active", "deleted_at", "deleted_by"])

            logger.info(
                f"Successfully soft deleted campaign: {campaign.pk} - {campaign_name} "
                f"by user {request.user}"
            )

            # Add success message
            messages.success(
                request,
                f"Campaign '{campaign_name}' has been deleted successfully.",
            )

            # Redirect to campaign list
            return redirect(reverse_lazy("civicpulse:campaign_list"))

        except Exception as e:
            logger.exception(f"Error deleting campaign {campaign.pk}: {e}")

            messages.error(
                request,
                "An error occurred while deleting the campaign. "
                "Please try again or contact support.",
            )

            # Redirect back to campaign detail page on error
            return redirect(reverse("civicpulse:campaign_detail", kwargs={"pk": pk}))
