"""
Comprehensive tests for Campaign views.

This module tests all Campaign-related views including:
- CampaignListView: Listing, search, filtering, pagination
- CampaignCreateView: Creation with duplicate detection and rate limiting
- CampaignDetailView: Display campaign details
- CampaignUpdateView: Edit existing campaigns
- CampaignDeleteView: Soft delete campaigns

Tests cover:
- Authentication requirements (LoginRequiredMixin)
- GET and POST requests
- Form validation
- Duplicate detection flow
- Rate limiting
- Query optimization (select_related/prefetch_related)
- Success/error messages
- Permission checks
- Edge cases and error conditions
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from civicpulse.models import Campaign, ContactAttempt, Person

User = get_user_model()


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def user(db):
    """Create a regular authenticated user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        role="organizer",
        organization="Test Org",
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="adminpass123",
        role="admin",
        organization="Admin Org",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def client_logged_in(client, user):
    """Return a logged-in client."""
    client.force_login(user)
    return client


@pytest.fixture
def campaign(db, user):
    """Create a test campaign."""
    return Campaign.objects.create(
        name="Test Campaign 2024",
        candidate_name="John Doe",
        election_date=date.today() + timedelta(days=30),
        status="active",
        organization="Test Organization",
        description="Test campaign description",
        created_by=user,
    )


@pytest.fixture
def past_campaign(db, user):
    """Create a campaign with past election date."""
    return Campaign.objects.create(
        name="Past Campaign 2023",
        candidate_name="Jane Smith",
        election_date=date.today() - timedelta(days=30),
        status="completed",
        organization="Test Organization",
        created_by=user,
    )


@pytest.fixture
def multiple_campaigns(db, user):
    """Create multiple campaigns for testing list view."""
    campaigns = []
    for i in range(25):  # More than paginate_by (20)
        campaigns.append(
            Campaign.objects.create(
                name=f"Campaign {i}",
                candidate_name=f"Candidate {i}",
                election_date=date.today() + timedelta(days=i),
                status="active" if i % 2 == 0 else "paused",
                organization=f"Org {i % 3}",  # 3 different orgs
                created_by=user,
            )
        )
    return campaigns


@pytest.fixture
def campaign_form_data():
    """Valid form data for campaign creation."""
    return {
        "name": "New Campaign 2025",
        "candidate_name": "Alice Johnson",
        "description": "A test campaign for local elections",
        "election_date": (date.today() + timedelta(days=60)).isoformat(),
        "status": "active",
        "organization": "New Organization",
    }


@pytest.fixture
def person(db, user):
    """Create a person for contact attempts."""
    return Person.objects.create(
        first_name="Test",
        last_name="Person",
        email="test@person.com",
        created_by=user,
    )


@pytest.fixture
def contact_attempt(db, user, campaign, person):
    """Create a contact attempt linked to a campaign."""
    return ContactAttempt.objects.create(
        person=person,
        campaign=campaign,
        contact_type="phone",
        contact_date=timezone.now(),
        contacted_by=user,
        result="contacted",
        notes="Test contact",
    )


# ============================================================================
# CampaignListView Tests
# ============================================================================


class TestCampaignListView:
    """Test CampaignListView functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up the list view URL."""
        self.url = reverse("civicpulse:campaign-list")

    def test_login_required(self, client):
        """Test that login is required to access the list view."""
        response = client.get(self.url)
        # Should redirect to login
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_get_campaign_list(self, client_logged_in, campaign):
        """Test GET request returns campaign list."""
        response = client_logged_in.get(self.url)

        assert response.status_code == 200
        assert "campaigns" in response.context
        assert campaign in response.context["campaigns"]
        assert response.context["page_title"] == "Campaigns"

    def test_only_active_campaigns_shown(self, client_logged_in, campaign, db, user):
        """Test that only active campaigns are displayed."""
        # Create a deleted campaign
        deleted_campaign = Campaign.objects.create(
            name="Deleted Campaign",
            candidate_name="Deleted Candidate",
            election_date=date.today() + timedelta(days=10),
            status="active",
            created_by=user,
            is_active=False,
        )

        response = client_logged_in.get(self.url)

        assert response.status_code == 200
        assert campaign in response.context["campaigns"]
        assert deleted_campaign not in response.context["campaigns"]

    def test_search_by_campaign_name(self, client_logged_in, multiple_campaigns):
        """Test search functionality by campaign name."""
        response = client_logged_in.get(self.url, {"q": "Campaign 5"})

        assert response.status_code == 200
        campaigns = list(response.context["campaigns"])
        assert len(campaigns) == 1
        assert campaigns[0].name == "Campaign 5"
        assert response.context["search_query"] == "Campaign 5"

    def test_search_by_candidate_name(self, client_logged_in, campaign):
        """Test search functionality by candidate name."""
        response = client_logged_in.get(self.url, {"q": "John Doe"})

        assert response.status_code == 200
        campaigns = list(response.context["campaigns"])
        assert len(campaigns) >= 1
        assert campaign in campaigns

    def test_search_case_insensitive(self, client_logged_in, campaign):
        """Test that search is case-insensitive."""
        response = client_logged_in.get(self.url, {"q": "JOHN DOE"})

        assert response.status_code == 200
        campaigns = list(response.context["campaigns"])
        assert campaign in campaigns

    def test_filter_by_status(self, client_logged_in, multiple_campaigns):
        """Test filtering by status."""
        response = client_logged_in.get(self.url, {"status": "active"})

        assert response.status_code == 200
        campaigns = list(response.context["campaigns"])
        for campaign in campaigns:
            assert campaign.status == "active"
        assert response.context["status_filter"] == "active"

    def test_filter_by_organization(self, client_logged_in, multiple_campaigns):
        """Test filtering by organization."""
        response = client_logged_in.get(self.url, {"organization": "Org 1"})

        assert response.status_code == 200
        campaigns = list(response.context["campaigns"])
        for campaign in campaigns:
            assert "Org 1" in campaign.organization

    def test_combined_search_and_filter(self, client_logged_in, multiple_campaigns):
        """Test combining search and filters."""
        response = client_logged_in.get(
            self.url, {"q": "Campaign", "status": "active", "organization": "Org 0"}
        )

        assert response.status_code == 200
        campaigns = list(response.context["campaigns"])
        for campaign in campaigns:
            assert campaign.status == "active"
            assert "Org 0" in campaign.organization

    def test_pagination(self, client_logged_in, multiple_campaigns):
        """Test pagination with 20 items per page."""
        response = client_logged_in.get(self.url)

        assert response.status_code == 200
        # Should have pagination
        assert "page_obj" in response.context
        page_obj = response.context["page_obj"]
        assert page_obj.paginator.per_page == 20
        assert len(response.context["campaigns"]) == 20

    def test_pagination_second_page(self, client_logged_in, multiple_campaigns):
        """Test accessing second page of results."""
        response = client_logged_in.get(self.url, {"page": 2})

        assert response.status_code == 200
        page_obj = response.context["page_obj"]
        assert page_obj.number == 2
        # Should have remaining items (25 total - 20 on first page = 5 on second)
        assert len(response.context["campaigns"]) == 5

    def test_ordering_newest_first(self, client_logged_in, multiple_campaigns):
        """Test campaigns are ordered by creation date (newest first)."""
        response = client_logged_in.get(self.url)

        assert response.status_code == 200
        campaigns = list(response.context["campaigns"])
        # Check that campaigns are in reverse chronological order
        for i in range(len(campaigns) - 1):
            assert campaigns[i].created_at >= campaigns[i + 1].created_at

    def test_query_optimization_select_related(
        self, client_logged_in, campaign, django_assert_num_queries
    ):
        """Test that select_related is used for created_by."""
        # Should use select_related for created_by to avoid N+1 queries
        # 7 queries total:
        # 1. Session lookup (auth)
        # 2. User lookup (auth)
        # 3. COUNT for pagination
        # 4. Main campaign query with select_related('created_by')
        # 5-7. Transaction management (SAVEPOINT, session update, RELEASE)
        with django_assert_num_queries(7):
            response = client_logged_in.get(self.url)
            campaigns = list(response.context["campaigns"])
            # Access created_by without additional queries
            for camp in campaigns:
                _ = camp.created_by.username

    def test_status_choices_in_context(self, client_logged_in):
        """Test that status choices are available in context."""
        response = client_logged_in.get(self.url)

        assert response.status_code == 200
        assert "status_choices" in response.context
        assert len(response.context["status_choices"]) > 0

    def test_empty_search_results(self, client_logged_in, campaign):
        """Test search with no matches."""
        response = client_logged_in.get(self.url, {"q": "NonexistentCampaign"})

        assert response.status_code == 200
        campaigns = list(response.context["campaigns"])
        assert len(campaigns) == 0


# ============================================================================
# CampaignCreateView Tests
# ============================================================================


class TestCampaignCreateView:
    """Test CampaignCreateView functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up the create view URL."""
        self.url = reverse("civicpulse:campaign-create")

    def test_login_required(self, client):
        """Test that login is required to access create view."""
        response = client.get(self.url)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_get_create_form(self, client_logged_in):
        """Test GET request returns create form."""
        response = client_logged_in.get(self.url)

        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["page_title"] == "Create New Campaign"
        assert response.context["submit_button_text"] == "Create Campaign"

    def test_create_campaign_success(self, client_logged_in, campaign_form_data, user):
        """Test successful campaign creation."""
        response = client_logged_in.post(self.url, campaign_form_data)

        # Should redirect to detail page
        assert response.status_code == 302
        assert "campaign" in response.url

        # Verify campaign was created
        campaign = Campaign.objects.get(name="New Campaign 2025")
        assert campaign.candidate_name == "Alice Johnson"
        assert campaign.created_by == user
        assert campaign.is_active is True

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        assert any("created successfully" in str(m) for m in messages)

    def test_create_campaign_invalid_data(self, client_logged_in):
        """Test campaign creation with invalid data."""
        invalid_data = {
            "name": "",  # Required field missing
            "candidate_name": "Test",
            "election_date": "invalid-date",
            "status": "active",
        }

        response = client_logged_in.post(self.url, invalid_data)

        # Should re-render form with errors
        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["form"].errors

        # Verify no campaign was created
        assert Campaign.objects.filter(candidate_name="Test").count() == 0

    def test_create_campaign_past_date(self, client_logged_in, campaign_form_data):
        """Test that new campaigns cannot have past election dates."""
        campaign_form_data["election_date"] = (
            date.today() - timedelta(days=10)
        ).isoformat()

        response = client_logged_in.post(self.url, campaign_form_data)

        # Should show validation error
        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["form"].errors
        assert "election_date" in response.context["form"].errors

    def test_duplicate_detection_shows_warning(
        self, client_logged_in, campaign, campaign_form_data
    ):
        """Test duplicate detection shows warning on first submission."""
        # Use similar data to existing campaign
        campaign_form_data["name"] = "Test Campaign 2024"
        campaign_form_data["candidate_name"] = "John Doe"
        campaign_form_data["election_date"] = campaign.election_date.isoformat()

        response = client_logged_in.post(self.url, campaign_form_data)

        # Should re-render form with duplicate warning
        assert response.status_code == 200
        assert "duplicates" in response.context
        assert "show_duplicate_warning" in response.context
        assert response.context["show_duplicate_warning"] is True

        # Check warning message
        messages = list(get_messages(response.wsgi_request))
        assert any("duplicate" in str(m).lower() for m in messages)

    def test_create_with_duplicate_confirmation(
        self, client_logged_in, campaign, campaign_form_data, user
    ):
        """Test creating campaign after confirming duplicates."""
        # Use similar data but confirm creation
        campaign_form_data["name"] = "Similar Campaign Name"
        campaign_form_data["candidate_name"] = "John Doe"
        campaign_form_data["election_date"] = campaign.election_date.isoformat()
        campaign_form_data["confirm_duplicates"] = "on"

        response = client_logged_in.post(self.url, campaign_form_data)

        # Should redirect to detail page
        assert response.status_code == 302

        # Verify campaign was created
        new_campaign = Campaign.objects.get(name="Similar Campaign Name")
        assert new_campaign.created_by == user

    @pytest.mark.django_db
    def test_rate_limiting(self, client_logged_in, campaign_form_data):
        """Test rate limiting on POST requests."""
        # This test mocks rate limiting to avoid making 20 actual requests
        with patch("django_ratelimit.decorators.is_ratelimited", return_value=True):
            response = client_logged_in.post(self.url, campaign_form_data)

            # Should return 403 Forbidden when rate limited
            assert response.status_code == 403

    def test_form_validation_error_handling(self, client_logged_in):
        """Test that validation errors are displayed properly."""
        invalid_data = {
            "name": "AB",  # Too short
            "candidate_name": "A",  # Too short
            "election_date": date.today().isoformat(),
            "status": "invalid_status",  # Invalid choice
        }

        response = client_logged_in.post(self.url, invalid_data)

        assert response.status_code == 200
        assert response.context["form"].errors
        # Check error message was added
        messages = list(get_messages(response.wsgi_request))
        assert any("correct the errors" in str(m).lower() for m in messages)

    def test_integrity_error_handling(self, client_logged_in, campaign_form_data, db):
        """Test handling of database integrity errors."""
        # First create a campaign
        Campaign.objects.create(
            name="Duplicate Campaign",
            candidate_name="Test",
            election_date=date.today() + timedelta(days=10),
            status="active",
        )

        # Try to create duplicate (same name)
        campaign_form_data["name"] = "Duplicate Campaign"

        with patch(
            "civicpulse.services.campaign_service.CampaignCreationService.create_campaign",
            side_effect=Exception("Database error"),
        ):
            response = client_logged_in.post(self.url, campaign_form_data)

            assert response.status_code == 200
            messages = list(get_messages(response.wsgi_request))
            assert any("error occurred" in str(m).lower() for m in messages)

    def test_sets_created_by(self, client_logged_in, campaign_form_data, user):
        """Test that created_by is set to current user."""
        client_logged_in.post(self.url, campaign_form_data)

        campaign = Campaign.objects.get(name="New Campaign 2025")
        assert campaign.created_by == user

    def test_xss_protection_in_fields(self, client_logged_in, campaign_form_data):
        """Test XSS protection through sanitization."""
        campaign_form_data["name"] = "<script>alert('xss')</script>Campaign"
        campaign_form_data["description"] = "<img src=x onerror=alert('xss')>"

        response = client_logged_in.post(self.url, campaign_form_data)

        if response.status_code == 302:
            campaign = Campaign.objects.get(candidate_name="Alice Johnson")
            # Should have sanitized the malicious content
            assert "<script>" not in campaign.name
            assert "onerror" not in campaign.description


# ============================================================================
# CampaignDetailView Tests
# ============================================================================


class TestCampaignDetailView:
    """Test CampaignDetailView functionality."""

    def test_login_required(self, client, campaign):
        """Test that login is required to access detail view."""
        url = reverse("civicpulse:campaign-detail", kwargs={"pk": campaign.pk})
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_get_campaign_detail(self, client_logged_in, campaign):
        """Test GET request returns campaign details."""
        url = reverse("civicpulse:campaign-detail", kwargs={"pk": campaign.pk})
        response = client_logged_in.get(url)

        assert response.status_code == 200
        assert response.context["campaign"] == campaign
        assert response.context["page_title"] == f"Campaign: {campaign.name}"

    def test_deleted_campaign_returns_404(self, client_logged_in, campaign):
        """Test that soft-deleted campaigns return 404."""
        campaign.is_active = False
        campaign.save()

        url = reverse("civicpulse:campaign-detail", kwargs={"pk": campaign.pk})
        response = client_logged_in.get(url)

        assert response.status_code == 404

    def test_nonexistent_campaign_returns_404(self, client_logged_in):
        """Test that non-existent campaign returns 404."""
        import uuid

        fake_uuid = uuid.uuid4()
        url = reverse("civicpulse:campaign-detail", kwargs={"pk": fake_uuid})
        response = client_logged_in.get(url)

        assert response.status_code == 404

    def test_election_timing_information_upcoming(self, client_logged_in, campaign):
        """Test that upcoming election information is in context."""
        url = reverse("civicpulse:campaign-detail", kwargs={"pk": campaign.pk})
        response = client_logged_in.get(url)

        assert response.status_code == 200
        assert "is_upcoming" in response.context
        assert "days_until_election" in response.context
        assert response.context["is_upcoming"] is True
        assert response.context["days_until_election"] is not None

    def test_election_timing_information_past(self, client_logged_in, past_campaign):
        """Test that past election information is in context."""
        url = reverse("civicpulse:campaign-detail", kwargs={"pk": past_campaign.pk})
        response = client_logged_in.get(url)

        assert response.status_code == 200
        assert response.context["is_upcoming"] is False
        assert response.context["days_until_election"] is None

    def test_query_optimization_prefetch_contact_attempts(
        self, client_logged_in, campaign, contact_attempt, django_assert_num_queries
    ):
        """Test that contact_attempts are prefetched with their related persons.

        Expected queries (9 total):
        1. Session lookup (authentication)
        2. User lookup (authentication)
        3. Campaign query (main object retrieval)
        4. Contact attempts + persons query (optimized with Prefetch + select_related)
        5. Target districts query (prefetch for district-based filtering)
        6. User lookup (duplicate - accessing created_by in template)
        7. SAVEPOINT (transaction management)
        8. UPDATE session (transaction management)
        9. RELEASE SAVEPOINT (transaction management)
        """
        url = reverse("civicpulse:campaign-detail", kwargs={"pk": campaign.pk})

        # Should use Prefetch with select_related for contact_attempts and persons
        # Also prefetches target_districts for district-based filtering
        with django_assert_num_queries(
            9
        ):  # Auth (2) + main (1) + contact prefetch (1) + districts prefetch (1) + duplicate user (1) + transaction (3)
            response = client_logged_in.get(url)
            campaign_obj = response.context["campaign"]
            # Access contact_attempts without additional queries
            _ = list(campaign_obj.contact_attempts.all())

    def test_displays_contact_attempts(
        self, client_logged_in, campaign, contact_attempt
    ):
        """Test that related contact attempts are accessible."""
        url = reverse("civicpulse:campaign-detail", kwargs={"pk": campaign.pk})
        response = client_logged_in.get(url)

        campaign_obj = response.context["campaign"]
        attempts = list(campaign_obj.contact_attempts.all())
        assert contact_attempt in attempts


# ============================================================================
# CampaignUpdateView Tests
# ============================================================================


class TestCampaignUpdateView:
    """Test CampaignUpdateView functionality."""

    def test_login_required(self, client, campaign):
        """Test that login is required to access update view."""
        url = reverse("civicpulse:campaign-edit", kwargs={"pk": campaign.pk})
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_get_update_form(self, client_logged_in, campaign):
        """Test GET request returns update form."""
        url = reverse("civicpulse:campaign-edit", kwargs={"pk": campaign.pk})
        response = client_logged_in.get(url)

        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["campaign"] == campaign
        assert response.context["page_title"] == f"Edit Campaign: {campaign.name}"
        assert response.context["submit_button_text"] == "Update Campaign"

    def test_update_campaign_success(self, client_logged_in, campaign):
        """Test successful campaign update."""
        url = reverse("civicpulse:campaign-edit", kwargs={"pk": campaign.pk})
        update_data = {
            "name": "Updated Campaign Name",
            "candidate_name": campaign.candidate_name,
            "description": "Updated description",
            "election_date": campaign.election_date.isoformat(),
            "status": "paused",
            "organization": campaign.organization,
        }

        response = client_logged_in.post(url, update_data)

        # Should redirect to detail page
        assert response.status_code == 302
        assert str(campaign.pk) in response.url

        # Verify campaign was updated
        campaign.refresh_from_db()
        assert campaign.name == "Updated Campaign Name"
        assert campaign.status == "paused"
        assert campaign.description == "Updated description"

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        assert any("updated successfully" in str(m).lower() for m in messages)

    def test_update_allows_past_election_date(self, client_logged_in, past_campaign):
        """Test that existing campaigns can keep past election dates."""
        url = reverse("civicpulse:campaign-edit", kwargs={"pk": past_campaign.pk})
        update_data = {
            "name": past_campaign.name,
            "candidate_name": past_campaign.candidate_name,
            "description": "Updated past campaign",
            "election_date": past_campaign.election_date.isoformat(),  # Past date
            "status": past_campaign.status,
            "organization": past_campaign.organization,
        }

        response = client_logged_in.post(url, update_data)

        # Should succeed since this is an existing campaign
        assert response.status_code == 302

        # Verify update was successful
        past_campaign.refresh_from_db()
        assert past_campaign.description == "Updated past campaign"

    def test_update_campaign_invalid_data(self, client_logged_in, campaign):
        """Test update with invalid data."""
        url = reverse("civicpulse:campaign-edit", kwargs={"pk": campaign.pk})
        invalid_data = {
            "name": "",  # Required field
            "candidate_name": campaign.candidate_name,
            "election_date": campaign.election_date.isoformat(),
            "status": "active",
        }

        response = client_logged_in.post(url, invalid_data)

        # Should re-render form with errors
        assert response.status_code == 200
        assert response.context["form"].errors

        # Verify campaign was not updated
        campaign.refresh_from_db()
        assert campaign.name == "Test Campaign 2024"

    def test_update_deleted_campaign_returns_404(self, client_logged_in, campaign):
        """Test that soft-deleted campaigns cannot be edited."""
        campaign.is_active = False
        campaign.save()

        url = reverse("civicpulse:campaign-edit", kwargs={"pk": campaign.pk})
        response = client_logged_in.get(url)

        assert response.status_code == 404

    def test_validation_error_handling(self, client_logged_in, campaign):
        """Test handling of validation errors."""
        url = reverse("civicpulse:campaign-edit", kwargs={"pk": campaign.pk})

        with patch(
            "civicpulse.services.campaign_service.CampaignCreationService.update_campaign",
            side_effect=Exception("Validation error"),
        ):
            update_data = {
                "name": campaign.name,
                "candidate_name": campaign.candidate_name,
                "election_date": campaign.election_date.isoformat(),
                "status": "active",
            }
            response = client_logged_in.post(url, update_data)

            assert response.status_code == 200
            messages = list(get_messages(response.wsgi_request))
            assert any("error occurred" in str(m).lower() for m in messages)

    @pytest.mark.django_db
    def test_rate_limiting(self, client_logged_in, campaign):
        """Test rate limiting on POST requests."""
        url = reverse("civicpulse:campaign-edit", kwargs={"pk": campaign.pk})

        with patch("django_ratelimit.decorators.is_ratelimited", return_value=True):
            update_data = {
                "name": campaign.name,
                "candidate_name": campaign.candidate_name,
                "election_date": campaign.election_date.isoformat(),
                "status": "active",
            }
            response = client_logged_in.post(url, update_data)

            # Should return 403 Forbidden when rate limited
            assert response.status_code == 403


# ============================================================================
# CampaignDeleteView Tests
# ============================================================================


class TestCampaignDeleteView:
    """Test CampaignDeleteView functionality."""

    def test_login_required_get(self, client, campaign):
        """Test that login is required to access delete confirmation."""
        url = reverse("civicpulse:campaign-delete", kwargs={"pk": campaign.pk})
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_login_required_post(self, client, campaign):
        """Test that login is required to delete."""
        url = reverse("civicpulse:campaign-delete", kwargs={"pk": campaign.pk})
        response = client.post(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_get_delete_confirmation(self, client_logged_in, campaign):
        """Test GET request returns confirmation page."""
        url = reverse("civicpulse:campaign-delete", kwargs={"pk": campaign.pk})
        response = client_logged_in.get(url)

        assert response.status_code == 200
        assert "campaign" in response.context
        assert response.context["campaign"] == campaign
        assert response.context["page_title"] == f"Delete Campaign: {campaign.name}"

    def test_soft_delete_campaign(self, client_logged_in, campaign, user):
        """Test successful soft delete of campaign."""
        url = reverse("civicpulse:campaign-delete", kwargs={"pk": campaign.pk})
        response = client_logged_in.post(url)

        # Should redirect to list page
        assert response.status_code == 302
        assert response.url == reverse("civicpulse:campaign-list")

        # Verify campaign was soft deleted
        campaign.refresh_from_db()
        assert campaign.is_active is False
        assert campaign.deleted_at is not None
        assert campaign.deleted_by == user

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        assert any("deleted successfully" in str(m).lower() for m in messages)

    def test_delete_already_deleted_campaign(self, client_logged_in, campaign):
        """Test that already deleted campaigns return 404."""
        campaign.is_active = False
        campaign.save()

        url = reverse("civicpulse:campaign-delete", kwargs={"pk": campaign.pk})
        response = client_logged_in.get(url)

        assert response.status_code == 404

    def test_delete_nonexistent_campaign(self, client_logged_in):
        """Test that non-existent campaign returns 404."""
        import uuid

        fake_uuid = uuid.uuid4()
        url = reverse("civicpulse:campaign-delete", kwargs={"pk": fake_uuid})
        response = client_logged_in.get(url)

        assert response.status_code == 404

    def test_delete_preserves_related_data(
        self, client_logged_in, campaign, contact_attempt
    ):
        """Test that soft delete preserves related contact attempts."""
        url = reverse("civicpulse:campaign-delete", kwargs={"pk": campaign.pk})
        response = client_logged_in.post(url)

        assert response.status_code == 302

        # Verify contact attempt still exists
        assert ContactAttempt.objects.filter(pk=contact_attempt.pk).exists()

    def test_error_handling_during_delete(self, client_logged_in, campaign):
        """Test error handling if delete fails."""
        url = reverse("civicpulse:campaign-delete", kwargs={"pk": campaign.pk})

        # Mock save to raise an exception
        with patch.object(Campaign, "save", side_effect=Exception("Database error")):
            response = client_logged_in.post(url)

            # Should redirect back to detail page
            assert response.status_code == 302
            assert str(campaign.pk) in response.url

            # Check error message
            messages = list(get_messages(response.wsgi_request))
            assert any("error occurred" in str(m).lower() for m in messages)

            # Verify campaign was not deleted
            campaign.refresh_from_db()
            assert campaign.is_active is True

    @pytest.mark.django_db
    def test_rate_limiting(self, client_logged_in, campaign):
        """Test rate limiting on POST requests."""
        url = reverse("civicpulse:campaign-delete", kwargs={"pk": campaign.pk})

        with patch("django_ratelimit.decorators.is_ratelimited", return_value=True):
            response = client_logged_in.post(url)

            # Should return 403 Forbidden when rate limited
            assert response.status_code == 403

    def test_audit_fields_populated(self, client_logged_in, campaign, user):
        """Test that deleted_at and deleted_by are set correctly."""
        url = reverse("civicpulse:campaign-delete", kwargs={"pk": campaign.pk})
        before_delete = timezone.now()
        client_logged_in.post(url)

        campaign.refresh_from_db()
        assert campaign.deleted_by == user
        assert campaign.deleted_at is not None
        assert campaign.deleted_at >= before_delete


# ============================================================================
# Edge Cases and Additional Tests
# ============================================================================


class TestCampaignViewsEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_uuid_returns_404(self, client_logged_in):
        """Test that invalid UUID in URL returns 404."""
        url = "/campaigns/invalid-uuid/"
        response = client_logged_in.get(url)

        assert response.status_code == 404

    def test_concurrent_delete_handling(self, client_logged_in, campaign, user):
        """Test handling of concurrent deletion."""
        url = reverse("civicpulse:campaign-delete", kwargs={"pk": campaign.pk})

        # Simulate another user deleting the campaign first
        campaign.is_active = False
        campaign.save()

        response = client_logged_in.post(url)

        # Should return 404 since campaign is already deleted
        assert response.status_code == 404

    def test_form_remembers_data_on_error(self, client_logged_in):
        """Test that form retains data when validation fails."""
        url = reverse("civicpulse:campaign-create")
        invalid_data = {
            "name": "AB",  # Too short
            "candidate_name": "Valid Name",
            "election_date": (date.today() + timedelta(days=30)).isoformat(),
            "status": "active",
            "organization": "Test Org",
        }

        response = client_logged_in.post(url, invalid_data)

        assert response.status_code == 200
        form = response.context["form"]
        # Form should retain valid data
        assert form.data["candidate_name"] == "Valid Name"
        assert form.data["organization"] == "Test Org"

    def test_multiple_duplicate_campaigns_shown(self, client_logged_in, user):
        """Test that multiple duplicate warnings are displayed."""
        # Create multiple similar campaigns
        for i in range(3):
            Campaign.objects.create(
                name=f"Duplicate Campaign {i}",
                candidate_name="John Smith",
                election_date=date.today() + timedelta(days=30),
                status="active",
                created_by=user,
            )

        url = reverse("civicpulse:campaign-create")
        form_data = {
            "name": "Another Duplicate Campaign",
            "candidate_name": "John Smith",
            "election_date": (date.today() + timedelta(days=30)).isoformat(),
            "status": "active",
        }

        response = client_logged_in.post(url, form_data)

        assert response.status_code == 200
        assert "duplicates" in response.context
        # Should show warning about duplicates
        messages = list(get_messages(response.wsgi_request))
        assert any("duplicate" in str(m).lower() for m in messages)
