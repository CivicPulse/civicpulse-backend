"""
Person views for CivicPulse application.

This module provides views for creating, viewing, and managing Person records:
- PersonCreateView: Create new persons with duplicate detection and rate limiting
- PersonDetailView: View person details

Features:
- Rate limiting to prevent abuse
- Duplicate detection with user confirmation flow
- Comprehensive error handling and user feedback
- Integration with PersonCreationService for business logic
- Secure, authenticated access only
"""

from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, FormView
from django_ratelimit.decorators import ratelimit
from loguru import logger

from civicpulse.forms import PersonForm
from civicpulse.models import Person
from civicpulse.services.person_service import PersonCreationService

if TYPE_CHECKING:
    from civicpulse.models import User
else:
    User = get_user_model()


@method_decorator(ratelimit(key="ip", rate="10/h", method="POST"), name="post")
@method_decorator(login_required, name="dispatch")
class PersonCreateView(LoginRequiredMixin, FormView):
    """
    View for creating new Person records with duplicate detection.

    This view handles the complete person creation workflow including:
    1. Form validation using PersonForm
    2. Duplicate detection using PersonCreationService
    3. User confirmation if duplicates are found
    4. Person creation via PersonCreationService
    5. Success/error feedback to user

    Features:
    - Rate limiting: 10 requests per hour per IP address
    - Duplicate warning: Shows potential duplicates before creation
    - User confirmation: Allows user to proceed despite duplicates
    - Audit trail: Records created_by user
    - Error handling: Graceful handling of validation and integrity errors

    Attributes:
        template_name: Path to the creation form template
        form_class: PersonForm for data validation
        success_url: URL pattern name for redirect after successful creation

    Example:
        In urls.py:
        >>> path('persons/create/', PersonCreateView.as_view(), name='person-create')

        In template:
        >>> <form method="post">
        ...   {% csrf_token %}
        ...   {{ form.as_p }}
        ...   <button type="submit">Create Person</button>
        ... </form>

    Note:
        - Requires authenticated user (@login_required)
        - Rate limited to prevent abuse (10 POST requests per hour)
        - Uses two-step process for duplicate handling:
          1. First submission: Show duplicates if found
          2. Second submission: Create despite duplicates if confirmed
    """

    template_name = "civicpulse/person/create.html"
    form_class = PersonForm

    def get_success_url(self) -> str:
        """
        Return URL to redirect to after successful person creation.

        Returns:
            URL string pointing to the person detail page
        """
        # Will be set in form_valid() after person is created
        return reverse("civicpulse:person_detail", kwargs={"pk": self.person.pk})

    def form_valid(self, form: PersonForm) -> HttpResponse:
        """
        Process valid form submission with duplicate detection flow.

        This method implements a two-step process:
        1. First submission: Check for duplicates and show warning
        2. Second submission (with confirm_duplicates): Create person

        Workflow:
        1. Check if user has confirmed duplicates
           (form data contains confirm_duplicates)
        2. If not confirmed and duplicates exist:
           - Add warning message
           - Re-render form with duplicate information
        3. If confirmed or no duplicates:
           - Create person via PersonCreationService
           - Set created_by to current user
           - Add success message
           - Redirect to person detail page

        Args:
            form: Validated PersonForm instance with cleaned data

        Returns:
            HttpResponse: Either redirect to success URL or re-rendered form
                with duplicate warnings

        Raises:
            ValidationError: Re-raised from PersonCreationService if validation fails
            IntegrityError: Re-raised if database constraints are violated

        Example:
            First submission (duplicates found):
            >>> # User submits form
            >>> # Form is valid, but duplicates are found
            >>> # form_valid() adds warning message and re-renders form
            >>> # Template shows: "Found 3 potential duplicates. Review and confirm."

            Second submission (user confirms):
            >>> # User checks "confirm_duplicates" and submits
            >>> # form_valid() creates person and redirects
            >>> # Success message: "Person 'John Doe' created successfully"
        """
        logger.info(f"Processing person creation form from user {self.request.user}")

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
                [f"{p.full_name} ({p.email or 'no email'})" for p in form.duplicates]
            )
            messages.warning(
                self.request,
                f"Found {len(form.duplicates)} potential duplicate(s): "
                f"{duplicate_names}. "
                f"Please review and confirm if you want to create this person anyway.",
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

            from civicpulse.services.person_service import PersonDataDict

            service = PersonCreationService()

            # Create person via service (handles all business logic)
            person, duplicates = service.create_person(
                person_data=cast(PersonDataDict, form.cleaned_data),
                created_by=cast(User, self.request.user),
                check_duplicates=False,  # Already checked in form.clean()
            )

            # Store person for get_success_url()
            self.person = person

            logger.info(
                f"Successfully created person: {person.pk} - {person.full_name} "
                f"by user {self.request.user}"
            )

            # Add success message
            messages.success(
                self.request,
                f"Person '{person.full_name}' created successfully. "
                f"You can now view and edit their information.",
            )

            # Redirect to person detail page
            return super().form_valid(form)

        except ValidationError as e:
            logger.error(f"Validation error creating person: {e}")

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
            logger.error(f"Database integrity error creating person: {e}")

            # Add user-friendly error message
            messages.error(
                self.request,
                "Unable to create person due to a database constraint. "
                "This person may already exist with the same name and date of birth.",
            )

            form.add_error(
                None,
                "A person with this name and date of birth already exists in "
                "the system.",
            )

            return self.form_invalid(form)

        except Exception as e:
            logger.exception(f"Unexpected error creating person: {e}")

            # Add generic error message
            messages.error(
                self.request,
                "An unexpected error occurred while creating the person. "
                "Please try again or contact support if the problem persists.",
            )

            form.add_error(
                None,
                "An unexpected error occurred. Please try again or contact support.",
            )

            return self.form_invalid(form)

    def form_invalid(self, form: PersonForm) -> HttpResponse:
        """
        Handle invalid form submission.

        Adds error message and logs validation errors for debugging.

        Args:
            form: Invalid PersonForm instance with errors

        Returns:
            HttpResponse: Re-rendered form with error messages
        """
        logger.warning(f"Person creation form invalid: {form.errors}")

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
                - duplicates: List of duplicate persons (if any)
                - show_duplicate_warning: Boolean flag for duplicate warning display
        """
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create New Person"
        context["submit_button_text"] = "Create Person"

        # Add duplicate information if present
        if "duplicates" in kwargs:
            context["duplicates"] = kwargs["duplicates"]
        if "show_duplicate_warning" in kwargs:
            context["show_duplicate_warning"] = kwargs["show_duplicate_warning"]

        return context


@method_decorator(login_required, name="dispatch")
class PersonDetailView(LoginRequiredMixin, DetailView):
    """
    View for displaying Person details.

    This view shows comprehensive information about a specific Person record,
    including:
    - Personal information (name, date of birth, gender)
    - Contact information (email, phone numbers)
    - Address information (street, city, state, ZIP)
    - Additional information (occupation, employer, tags, notes)
    - Audit information (created_by, created_at, updated_at)

    Features:
    - Authenticated access only
    - Automatic 404 for non-existent or soft-deleted persons
    - Context includes person object for template rendering

    Attributes:
        model: Person model class
        template_name: Path to the detail template
        context_object_name: Name of the person object in template context

    Example:
        In urls.py:
        >>> path('persons/<uuid:pk>/', PersonDetailView.as_view(), name='person-detail')

        In template:
        >>> <h1>{{ person.full_name }}</h1>
        >>> <p>Email: {{ person.email }}</p>
        >>> <p>Phone: {{ person.phone_primary }}</p>

    Note:
        - Requires authenticated user (@login_required)
        - Uses UUID primary key (pk) in URL
        - Automatically filters out soft-deleted persons (is_active=True)
        - Returns 404 if person doesn't exist or is deleted
    """

    model = Person
    template_name = "civicpulse/person/detail.html"
    context_object_name = "person"

    def get_queryset(self):
        """
        Filter queryset to only return active persons with optimized queries.

        Returns:
            QuerySet of Person objects where is_active=True,
            with prefetch_related for person_districts, districts,
            and officeholders

        Note:
            This ensures soft-deleted persons (is_active=False) return 404
        """
        return Person.objects.filter(is_active=True).prefetch_related(
            "person_districts",  # Prefetch PersonDistrict junction records
            "person_districts__district",  # Prefetch the District for each junction
            "person_districts__district__officeholders",  # Prefetch officeholders
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Add additional context data to template.

        Args:
            **kwargs: Additional context from parent class

        Returns:
            Context dictionary with additional keys:
                - page_title: Title for the page (includes person's name)
                - districts: List of districts this person belongs to
                - district_officeholders: Dictionary mapping district IDs
                    to their officeholders
        """
        context = super().get_context_data(**kwargs)
        person = self.get_object()
        context["page_title"] = f"Person: {person.full_name}"

        # Get all districts for this person (already prefetched)
        person_districts = list(person.person_districts.all())
        districts = [pd.district for pd in person_districts]
        context["districts"] = districts

        # Build a dictionary of district ID to officeholders for template use
        district_officeholders = {}
        for district in districts:
            # Officeholders are already prefetched
            district_officeholders[district.id] = list(district.officeholders.all())

        context["district_officeholders"] = district_officeholders

        logger.info(
            f"User {self.request.user} viewed person: {person.pk} - "
            f"{person.full_name}, in {len(districts)} district(s)"
        )

        return context
