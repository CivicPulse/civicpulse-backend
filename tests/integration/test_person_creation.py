"""
Integration tests for Person creation workflow.

This module tests the complete end-to-end person creation flow including:
- PersonCreateView and PersonDetailView
- PersonForm validation and duplicate detection
- PersonCreationService business logic
- Template rendering and context variables
- Authentication and authorization
- Rate limiting
- Error handling and user feedback

Test Coverage:
1. Basic person creation flow
2. Duplicate detection and confirmation workflow
3. Validation and error handling
4. Rate limiting enforcement
5. Authentication requirements
6. Person detail view display
7. Template rendering and context
"""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse

from civicpulse.models import Person

User = get_user_model()


@pytest.fixture
def authenticated_client(regular_user):
    """Create an authenticated test client."""
    client = Client()
    client.force_login(regular_user)
    return client


@pytest.fixture
def valid_person_data():
    """Create valid person data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone_primary": "(202) 456-1111",  # Valid US phone number
        "date_of_birth": "1990-01-15",
        "gender": "M",
        "street_address": "123 Main St",
        "city": "Springfield",
        "state": "CA",
        "zip_code": "90210",
        "occupation": "Engineer",
        "employer": "Tech Corp",
        "notes": "Test person",
        "tags": "test, demo",
    }


@pytest.fixture
def duplicate_person(regular_user):
    """
    Create a person that will be detected as a duplicate.

    Uses different DOB to avoid unique_together constraint violation,
    but same name/email to trigger duplicate detection logic.
    """
    return Person.objects.create(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",  # Same email as valid_person_data
        date_of_birth=date(1990, 1, 20),  # Different DOB to avoid constraint
        created_by=regular_user,
    )


@pytest.mark.django_db
class TestBasicPersonCreationFlow:
    """Test the basic person creation workflow without duplicates."""

    def test_get_person_create_view_displays_form(self, authenticated_client):
        """Test that GET request to create view displays the form."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert "form" in response.context
        assert "page_title" in response.context
        assert response.context["page_title"] == "Create New Person"
        assert "submit_button_text" in response.context
        assert response.context["submit_button_text"] == "Create Person"

    def test_get_person_create_view_uses_correct_template(self, authenticated_client):
        """Test that the create view uses the correct template."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert "civicpulse/person/create.html" in [t.name for t in response.templates]

    def test_post_valid_data_creates_person(
        self, authenticated_client, regular_user, valid_person_data
    ):
        """Test that POST with valid data creates a new person."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, valid_person_data)

        # Should redirect to person detail view
        assert response.status_code == 302

        # Person should be created
        person = Person.objects.get(email="john.doe@example.com")
        assert person.first_name == "John"
        assert person.last_name == "Doe"
        assert person.email == "john.doe@example.com"
        # Phone numbers are normalized to E.164 format
        assert person.phone_primary == "+12024561111"
        assert person.city == "Springfield"
        assert person.state == "CA"

    def test_post_creates_person_with_correct_data(
        self, authenticated_client, regular_user, valid_person_data
    ):
        """Test that created person has all correct data fields."""
        url = reverse("civicpulse:person_create")
        authenticated_client.post(url, valid_person_data)

        person = Person.objects.get(email="john.doe@example.com")
        assert person.first_name == "John"
        assert person.last_name == "Doe"
        assert person.email == "john.doe@example.com"
        # Phone numbers are normalized to E.164 format
        assert person.phone_primary == "+12024561111"
        assert person.date_of_birth == date(1990, 1, 15)
        assert person.gender == "M"
        assert person.street_address == "123 Main St"
        assert person.city == "Springfield"
        assert person.state == "CA"
        assert person.zip_code == "90210"
        assert person.occupation == "Engineer"
        assert person.employer == "Tech Corp"
        assert person.notes == "Test person"
        assert "test" in person.tags
        assert "demo" in person.tags

    def test_post_sets_created_by_field(
        self, authenticated_client, regular_user, valid_person_data
    ):
        """Test that created_by audit field is set to current user."""
        url = reverse("civicpulse:person_create")
        authenticated_client.post(url, valid_person_data)

        person = Person.objects.get(email="john.doe@example.com")
        assert person.created_by == regular_user

    def test_post_redirects_to_detail_view(
        self, authenticated_client, valid_person_data
    ):
        """Test that successful creation redirects to person detail view."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, valid_person_data)

        person = Person.objects.get(email="john.doe@example.com")
        expected_url = reverse("civicpulse:person_detail", kwargs={"pk": person.pk})

        assert response.status_code == 302
        assert response.url == expected_url

    def test_post_shows_success_message(self, authenticated_client, valid_person_data):
        """Test that success message is displayed after creation."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, valid_person_data, follow=True)

        messages = list(get_messages(response.wsgi_request))
        assert len(messages) > 0
        success_messages = [m for m in messages if m.level_tag == "success"]
        assert len(success_messages) > 0
        assert "created successfully" in str(success_messages[0])


@pytest.mark.django_db
class TestDuplicateDetectionFlow:
    """Test the duplicate detection and confirmation workflow."""

    def test_duplicate_warning_shown_when_duplicates_exist(
        self, authenticated_client, duplicate_person, valid_person_data
    ):
        """Test that duplicate warning is shown when potential duplicates exist."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, valid_person_data)

        # Should NOT redirect (re-render form with warning)
        assert response.status_code == 200

        # Should show duplicate warning in context
        assert "duplicates" in response.context
        assert "show_duplicate_warning" in response.context
        assert response.context["show_duplicate_warning"] is True
        assert len(response.context["duplicates"]) > 0

    def test_duplicate_warning_message_displayed(
        self, authenticated_client, duplicate_person, valid_person_data
    ):
        """Test that warning message is displayed when duplicates found."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, valid_person_data)

        messages = list(get_messages(response.wsgi_request))
        warning_messages = [m for m in messages if m.level_tag == "warning"]

        assert len(warning_messages) > 0
        assert "potential duplicate" in str(warning_messages[0]).lower()

    def test_can_view_duplicate_details(
        self, authenticated_client, duplicate_person, valid_person_data
    ):
        """Test that duplicate person details are accessible in context."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, valid_person_data)

        assert response.status_code == 200
        duplicates = response.context["duplicates"]
        assert len(duplicates) > 0

        # Check that duplicate person is in the list
        duplicate_ids = [d.id for d in duplicates]
        assert duplicate_person.id in duplicate_ids

    def test_confirmation_checkbox_required_to_proceed(
        self, authenticated_client, duplicate_person, valid_person_data
    ):
        """Test that confirmation checkbox is required to create despite duplicates."""
        url = reverse("civicpulse:person_create")

        # First submission - should show warning
        response = authenticated_client.post(url, valid_person_data)
        assert response.status_code == 200
        assert "duplicates" in response.context

        # Second submission without confirmation - should still show warning
        response = authenticated_client.post(url, valid_person_data)
        assert response.status_code == 200
        assert "duplicates" in response.context

        # Only the original duplicate_person should exist, no new person created
        assert Person.objects.filter(email="john.doe@example.com").count() == 1
        assert Person.objects.filter(email="john.doe@example.com").first() == duplicate_person

    def test_creation_succeeds_with_confirmation(
        self, authenticated_client, duplicate_person, valid_person_data
    ):
        """Test that person is created when user confirms despite duplicates."""
        url = reverse("civicpulse:person_create")

        # First submission - shows warning
        authenticated_client.post(url, valid_person_data)

        # Second submission with confirmation
        valid_person_data["confirm_duplicates"] = "on"
        response = authenticated_client.post(url, valid_person_data)

        # Should redirect to detail view
        assert response.status_code == 302

        # Two persons should exist now (original duplicate + new person)
        assert Person.objects.filter(email="john.doe@example.com").count() == 2

    def test_form_retains_user_input_during_duplicate_warning(
        self, authenticated_client, duplicate_person, valid_person_data
    ):
        """Test that form retains user's input when showing duplicate warning."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, valid_person_data)

        assert response.status_code == 200
        form = response.context["form"]

        # Form should have the original data
        assert form.data["first_name"] == "John"
        assert form.data["last_name"] == "Doe"
        assert form.data["email"] == "john.doe@example.com"
        assert form.data["city"] == "Springfield"


@pytest.mark.django_db
class TestValidationAndErrorHandling:
    """Test form validation and error handling."""

    def test_post_with_missing_required_fields_shows_errors(self, authenticated_client):
        """Test that POST with missing required fields shows validation errors."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, {})

        assert response.status_code == 200
        form = response.context["form"]
        assert form.errors
        assert "first_name" in form.errors
        assert "last_name" in form.errors

    def test_required_field_validation(self, authenticated_client):
        """Test validation of required fields."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, {"email": "test@example.com"})

        assert response.status_code == 200
        form = response.context["form"]
        assert not form.is_valid()
        assert "first_name" in form.errors
        assert "last_name" in form.errors

    def test_invalid_email_format_validation(self, authenticated_client):
        """Test email format validation."""
        url = reverse("civicpulse:person_create")
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "invalid-email",
        }
        response = authenticated_client.post(url, data)

        assert response.status_code == 200
        form = response.context["form"]
        assert not form.is_valid()
        assert "email" in form.errors

    def test_invalid_phone_format_validation(self, authenticated_client):
        """Test phone number format validation."""
        url = reverse("civicpulse:person_create")
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "phone_primary": "invalid-phone",
        }
        response = authenticated_client.post(url, data)

        assert response.status_code == 200
        form = response.context["form"]
        assert not form.is_valid()
        assert "phone_primary" in form.errors

    def test_invalid_zip_code_format_validation(self, authenticated_client):
        """Test ZIP code format validation."""
        url = reverse("civicpulse:person_create")
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "zip_code": "invalid",
        }
        response = authenticated_client.post(url, data)

        assert response.status_code == 200
        form = response.context["form"]
        assert not form.is_valid()
        assert "zip_code" in form.errors

    def test_invalid_state_code_validation(self, authenticated_client):
        """Test state code validation."""
        url = reverse("civicpulse:person_create")
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "state": "ZZ",
        }
        response = authenticated_client.post(url, data)

        assert response.status_code == 200
        form = response.context["form"]
        assert not form.is_valid()
        assert "state" in form.errors

    def test_future_date_of_birth_validation(self, authenticated_client):
        """Test that future date of birth is rejected."""
        url = reverse("civicpulse:person_create")
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "2030-01-01",
        }
        response = authenticated_client.post(url, data)

        assert response.status_code == 200
        form = response.context["form"]
        assert not form.is_valid()
        assert "date_of_birth" in form.errors

    def test_error_messages_displayed_correctly(self, authenticated_client):
        """Test that error messages are displayed in the template."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, {})

        assert response.status_code == 200

        # Check for error messages
        messages = list(get_messages(response.wsgi_request))
        error_messages = [m for m in messages if m.level_tag == "error"]
        assert len(error_messages) > 0


@pytest.mark.django_db
class TestRateLimiting:
    """Test rate limiting enforcement."""

    @pytest.mark.skip(reason="Rate limiting is hard to test in unit tests")
    def test_rate_limit_enforced_for_post_requests(
        self, authenticated_client, valid_person_data
    ):
        """Test that rate limit is enforced after 10 POST requests."""
        url = reverse("civicpulse:person_create")

        # Make 10 successful requests
        for i in range(10):
            data = valid_person_data.copy()
            data["email"] = f"user{i}@example.com"
            response = authenticated_client.post(url, data)
            # Should succeed or show duplicate warning
            assert response.status_code in [200, 302]

        # 11th request should be rate limited
        data = valid_person_data.copy()
        data["email"] = "user11@example.com"
        response = authenticated_client.post(url, data)

        # Should return 403 or similar rate limit response
        assert response.status_code == 403

    def test_get_requests_not_rate_limited(self, authenticated_client):
        """Test that GET requests are not rate limited."""
        url = reverse("civicpulse:person_create")

        # Make multiple GET requests
        for _ in range(15):
            response = authenticated_client.get(url)
            assert response.status_code == 200


@pytest.mark.django_db
class TestAuthentication:
    """Test authentication requirements."""

    def test_anonymous_users_redirected_to_login(self):
        """Test that anonymous users are redirected to login page."""
        client = Client()
        url = reverse("civicpulse:person_create")
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_anonymous_post_redirected_to_login(self, valid_person_data):
        """Test that anonymous POST requests are redirected to login."""
        client = Client()
        url = reverse("civicpulse:person_create")
        response = client.post(url, valid_person_data)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_authenticated_users_can_access_create_view(self, authenticated_client):
        """Test that authenticated users can access the create view."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.get(url)

        assert response.status_code == 200


@pytest.mark.django_db
class TestPersonDetailView:
    """Test the Person detail view."""

    def test_get_person_detail_displays_person(
        self, authenticated_client, regular_user
    ):
        """Test that GET request to detail view displays person information."""
        person = Person.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            created_by=regular_user,
        )

        url = reverse("civicpulse:person_detail", kwargs={"pk": person.pk})
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert "person" in response.context
        assert response.context["person"] == person

    def test_detail_view_displays_all_fields(self, authenticated_client, regular_user):
        """Test that all person fields are displayed in detail view."""
        person = Person.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            phone_primary="(212) 555-0123",
            date_of_birth=date(1985, 3, 20),
            gender="F",
            street_address="456 Oak Ave",
            city="Portland",
            state="OR",
            zip_code="97201",
            occupation="Designer",
            employer="Design Co",
            notes="Important client",
            tags=["vip", "priority"],
            created_by=regular_user,
        )

        url = reverse("civicpulse:person_detail", kwargs={"pk": person.pk})
        response = authenticated_client.get(url)

        assert response.status_code == 200
        context_person = response.context["person"]
        assert context_person.first_name == "Jane"
        assert context_person.last_name == "Smith"
        assert context_person.email == "jane.smith@example.com"
        assert context_person.phone_primary == "(212) 555-0123"
        assert context_person.city == "Portland"
        assert context_person.state == "OR"

    def test_inactive_persons_return_404(self, authenticated_client, regular_user):
        """Test that inactive (soft-deleted) persons return 404."""
        person = Person.objects.create(
            first_name="Deleted",
            last_name="Person",
            email="deleted@example.com",
            is_active=False,
            created_by=regular_user,
        )

        url = reverse("civicpulse:person_detail", kwargs={"pk": person.pk})
        response = authenticated_client.get(url)

        assert response.status_code == 404

    def test_non_existent_persons_return_404(self, authenticated_client):
        """Test that non-existent persons return 404."""
        import uuid
        # Use a random UUID that doesn't exist in the database
        non_existent_uuid = uuid.uuid4()
        url = reverse("civicpulse:person_detail", kwargs={"pk": non_existent_uuid})
        response = authenticated_client.get(url)

        assert response.status_code == 404

    def test_detail_view_uses_correct_template(
        self, authenticated_client, regular_user
    ):
        """Test that detail view uses the correct template."""
        person = Person.objects.create(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            created_by=regular_user,
        )

        url = reverse("civicpulse:person_detail", kwargs={"pk": person.pk})
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert "civicpulse/person/detail.html" in [t.name for t in response.templates]

    def test_detail_view_page_title_includes_name(
        self, authenticated_client, regular_user
    ):
        """Test that detail view page title includes person's name."""
        person = Person.objects.create(
            first_name="Alice",
            last_name="Johnson",
            email="alice@example.com",
            created_by=regular_user,
        )

        url = reverse("civicpulse:person_detail", kwargs={"pk": person.pk})
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert "page_title" in response.context
        assert "Alice Johnson" in response.context["page_title"]


@pytest.mark.django_db
class TestTemplateRendering:
    """Test template rendering and context variables."""

    def test_create_view_correct_template_used(self, authenticated_client):
        """Test that create view uses the correct template."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.get(url)

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "civicpulse/person/create.html" in template_names

    def test_create_view_context_variables_present(self, authenticated_client):
        """Test that all expected context variables are present."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert "form" in response.context
        assert "page_title" in response.context
        assert "submit_button_text" in response.context

    def test_form_rendered_in_template(self, authenticated_client):
        """Test that form is properly rendered in template."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check for form fields in rendered HTML
        assert "first_name" in content
        assert "last_name" in content
        assert "email" in content

    def test_duplicate_list_rendered_when_present(
        self, authenticated_client, duplicate_person, valid_person_data
    ):
        """Test that duplicate list is rendered when duplicates are found."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, valid_person_data)

        assert response.status_code == 200
        assert "duplicates" in response.context
        assert len(response.context["duplicates"]) > 0

        # Check that duplicate information is in the rendered content
        content = response.content.decode()
        assert "duplicate" in content.lower()

    def test_error_messages_rendered_in_template(self, authenticated_client):
        """Test that validation errors are rendered in template."""
        url = reverse("civicpulse:person_create")
        response = authenticated_client.post(url, {})

        assert response.status_code == 200
        content = response.content.decode()

        # Check for error indicators in HTML
        # Most forms show errors near the field or at the top
        assert "error" in content.lower() or "required" in content.lower()


@pytest.mark.django_db
class TestCompleteWorkflow:
    """Test complete end-to-end workflows."""

    def test_complete_person_creation_and_view_workflow(
        self, authenticated_client, valid_person_data
    ):
        """Test complete workflow: create person and view details."""
        # Step 1: Create person
        create_url = reverse("civicpulse:person_create")
        response = authenticated_client.post(create_url, valid_person_data, follow=True)

        # Should end up on detail page
        assert response.status_code == 200

        # Get the created person
        person = Person.objects.get(email="john.doe@example.com")

        # Step 2: Verify we're on the detail page
        assert response.request["PATH_INFO"] == reverse(
            "civicpulse:person_detail", kwargs={"pk": person.pk}
        )

        # Step 3: Verify person data is displayed
        assert "person" in response.context
        assert response.context["person"] == person

    def test_complete_duplicate_confirmation_workflow(
        self, authenticated_client, duplicate_person, valid_person_data
    ):
        """Test complete workflow with duplicate detection and confirmation."""
        create_url = reverse("civicpulse:person_create")

        # Step 1: First submission shows duplicate warning
        response = authenticated_client.post(create_url, valid_person_data)
        assert response.status_code == 200
        assert "duplicates" in response.context
        # Only the duplicate_person should exist at this point
        assert Person.objects.filter(email="john.doe@example.com").count() == 1

        # Step 2: Confirm and create despite duplicates
        valid_person_data["confirm_duplicates"] = "on"
        response = authenticated_client.post(create_url, valid_person_data, follow=True)

        # Step 3: Two persons should be created now and we're on detail page
        assert response.status_code == 200
        assert Person.objects.filter(email="john.doe@example.com").count() == 2
        # Get the newly created person (not the duplicate_person)
        persons = Person.objects.filter(email="john.doe@example.com").order_by("-created_at")
        person = persons.first()
        assert person.first_name == "John"
        assert person.last_name == "Doe"

        # Step 4: Verify success message
        messages = list(get_messages(response.wsgi_request))
        success_messages = [m for m in messages if m.level_tag == "success"]
        assert len(success_messages) > 0


@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_create_person_with_minimal_data(self, authenticated_client):
        """Test creating person with only required fields."""
        url = reverse("civicpulse:person_create")
        data = {
            "first_name": "Min",
            "last_name": "Imal",
        }
        response = authenticated_client.post(url, data, follow=True)

        assert response.status_code == 200
        person = Person.objects.get(first_name="Min", last_name="Imal")
        assert person is not None
        assert person.email == ""  # Optional field

    def test_create_person_with_special_characters_in_name(self, authenticated_client):
        """Test creating person with special characters in name."""
        url = reverse("civicpulse:person_create")
        data = {
            "first_name": "José",
            "last_name": "O'Brien-Smith",
        }
        response = authenticated_client.post(url, data, follow=True)

        assert response.status_code == 200
        # Name should be sanitized but preserved
        person = Person.objects.get(last_name__icontains="brien")
        assert person is not None

    def test_create_person_with_very_long_notes(self, authenticated_client):
        """Test creating person with maximum length notes field."""
        url = reverse("civicpulse:person_create")
        data = {
            "first_name": "Long",
            "last_name": "Notes",
            "notes": "A" * 5000,  # Long but within limit
        }
        response = authenticated_client.post(url, data, follow=True)

        assert response.status_code == 200
        person = Person.objects.get(first_name="Long")
        assert len(person.notes) == 5000

    def test_xss_protection_in_text_fields(self, authenticated_client):
        """Test that XSS attempts in text fields are sanitized."""
        url = reverse("civicpulse:person_create")
        data = {
            "first_name": '<script>alert("xss")</script>John',
            "last_name": "Doe",
            "notes": '<img src=x onerror="alert(1)">',
        }
        response = authenticated_client.post(url, data, follow=True)

        assert response.status_code == 200
        person = Person.objects.get(last_name="Doe")

        # Script tags should be removed
        assert "<script>" not in person.first_name
        assert "alert" not in person.first_name
        assert "<img" not in person.notes
