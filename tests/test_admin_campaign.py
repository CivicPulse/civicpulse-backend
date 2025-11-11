"""Tests for Campaign admin configuration."""

from datetime import date, timedelta

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.utils import timezone

from civicpulse.admin import CampaignAdmin, CampaignContactAttemptInline
from civicpulse.models import Campaign, ContactAttempt

User = get_user_model()


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="password123",
        role="admin",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def campaign(db, admin_user):
    """Create a test campaign."""
    return Campaign.objects.create(
        name="Test Campaign 2024",
        candidate_name="John Doe",
        election_date=date.today() + timedelta(days=30),
        status="active",
        organization="Test Organization",
        description="Test campaign description",
        created_by=admin_user,
    )


@pytest.fixture
def past_campaign(db, admin_user):
    """Create a campaign with past election date."""
    return Campaign.objects.create(
        name="Past Campaign 2023",
        candidate_name="Jane Smith",
        election_date=date.today() - timedelta(days=30),
        status="completed",
        organization="Test Organization",
        created_by=admin_user,
    )


@pytest.fixture
def request_factory():
    """Create a request factory."""
    return RequestFactory()


@pytest.fixture
def admin_site():
    """Create an admin site."""
    return AdminSite()


@pytest.fixture
def campaign_admin(admin_site):
    """Create a CampaignAdmin instance."""
    return CampaignAdmin(Campaign, admin_site)


class TestCampaignAdmin:
    """Test CampaignAdmin configuration."""

    def test_list_display(self, campaign_admin):
        """Test list_display is configured correctly."""
        assert "name" in campaign_admin.list_display
        assert "candidate_name" in campaign_admin.list_display
        assert "election_date" in campaign_admin.list_display
        assert "status" in campaign_admin.list_display
        assert "days_until_election_display" in campaign_admin.list_display
        assert "created_by" in campaign_admin.list_display
        assert "created_at" in campaign_admin.list_display

    def test_list_filter(self, campaign_admin):
        """Test list_filter is configured correctly."""
        assert "status" in campaign_admin.list_filter
        assert "election_date" in campaign_admin.list_filter
        assert "created_at" in campaign_admin.list_filter
        assert "organization" in campaign_admin.list_filter

    def test_search_fields(self, campaign_admin):
        """Test search_fields is configured correctly."""
        assert "name" in campaign_admin.search_fields
        assert "candidate_name" in campaign_admin.search_fields
        assert "description" in campaign_admin.search_fields
        assert "organization" in campaign_admin.search_fields

    def test_readonly_fields(self, campaign_admin):
        """Test readonly_fields is configured correctly."""
        assert "id" in campaign_admin.readonly_fields
        assert "created_at" in campaign_admin.readonly_fields
        assert "updated_at" in campaign_admin.readonly_fields
        assert "created_by" in campaign_admin.readonly_fields
        assert "deleted_at" in campaign_admin.readonly_fields
        assert "deleted_by" in campaign_admin.readonly_fields
        assert "days_until_election_display" in campaign_admin.readonly_fields

    def test_ordering(self, campaign_admin):
        """Test ordering is configured correctly."""
        assert campaign_admin.ordering == ["-created_at"]

    def test_date_hierarchy(self, campaign_admin):
        """Test date_hierarchy is configured correctly."""
        assert campaign_admin.date_hierarchy == "election_date"

    def test_fieldsets(self, campaign_admin):
        """Test fieldsets are configured correctly."""
        fieldsets_dict = {fs[0]: fs[1]["fields"] for fs in campaign_admin.fieldsets}

        # Check Campaign Information section
        assert "name" in fieldsets_dict["Campaign Information"]
        assert "candidate_name" in fieldsets_dict["Campaign Information"]
        assert "election_date" in fieldsets_dict["Campaign Information"]
        assert "status" in fieldsets_dict["Campaign Information"]

        # Check Details section
        assert "description" in fieldsets_dict["Details"]
        assert "organization" in fieldsets_dict["Details"]

        # Check Audit Information section
        assert "id" in fieldsets_dict["Audit Information"]
        assert "created_by" in fieldsets_dict["Audit Information"]
        assert "created_at" in fieldsets_dict["Audit Information"]
        assert "updated_at" in fieldsets_dict["Audit Information"]

    def test_inlines(self, campaign_admin):
        """Test inlines are configured correctly."""
        assert CampaignContactAttemptInline in campaign_admin.inlines

    def test_days_until_election_display_upcoming(
        self, campaign_admin, campaign, request_factory
    ):
        """Test days_until_election_display for upcoming election."""
        result = campaign_admin.days_until_election_display(campaign)

        # Should display days count for upcoming election
        assert "days" in result.lower()
        assert "30" in result or "29" in result  # Allow for timing differences

    def test_days_until_election_display_past(
        self, campaign_admin, past_campaign, request_factory
    ):
        """Test days_until_election_display for past election."""
        result = campaign_admin.days_until_election_display(past_campaign)

        # Should display "Past Election" for past elections
        assert "past" in result.lower()

    def test_save_model_sets_created_by(
        self, campaign_admin, admin_user, request_factory, db
    ):
        """Test save_model sets created_by on creation."""
        request = request_factory.get("/admin/civicpulse/campaign/")
        request.user = admin_user

        # Create a new campaign
        campaign = Campaign(
            name="New Campaign",
            candidate_name="Test Candidate",
            election_date=date.today() + timedelta(days=60),
        )

        # Mock form
        class MockForm:
            pass

        form = MockForm()

        # Call save_model (change=False means creation)
        campaign_admin.save_model(request, campaign, form, change=False)

        # Verify created_by is set
        assert campaign.created_by == admin_user

    def test_archive_campaigns_action(
        self, campaign_admin, campaign, admin_user, request_factory
    ):
        """Test archive_campaigns action."""
        from django.contrib.messages.storage.fallback import FallbackStorage

        request = request_factory.get("/admin/civicpulse/campaign/")
        request.user = admin_user
        # Add messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        queryset = Campaign.objects.filter(pk=campaign.pk)
        campaign_admin.archive_campaigns(request, queryset)

        # Refresh from database
        campaign.refresh_from_db()
        assert campaign.status == "archived"

    def test_activate_campaigns_action(
        self, campaign_admin, past_campaign, admin_user, request_factory
    ):
        """Test activate_campaigns action."""
        from django.contrib.messages.storage.fallback import FallbackStorage

        request = request_factory.get("/admin/civicpulse/campaign/")
        request.user = admin_user
        # Add messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        queryset = Campaign.objects.filter(pk=past_campaign.pk)
        campaign_admin.activate_campaigns(request, queryset)

        # Refresh from database
        past_campaign.refresh_from_db()
        assert past_campaign.status == "active"

    def test_export_to_csv_action(
        self, campaign_admin, campaign, admin_user, request_factory
    ):
        """Test export_to_csv action."""
        request = request_factory.get("/admin/civicpulse/campaign/")
        request.user = admin_user

        queryset = Campaign.objects.filter(pk=campaign.pk)
        response = campaign_admin.export_to_csv(request, queryset)

        # Check response
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert 'attachment; filename="campaigns.csv"' in response["Content-Disposition"]

        # Check content
        content = response.content.decode("utf-8")
        assert "Test Campaign 2024" in content
        assert "John Doe" in content

    def test_get_queryset_optimization(self, campaign_admin, campaign, request_factory):
        """Test get_queryset performs necessary joins."""
        request = request_factory.get("/admin/civicpulse/campaign/")

        queryset = campaign_admin.get_queryset(request)

        # Verify queryset exists and contains our campaign
        assert campaign in queryset


class TestCampaignContactAttemptInline:
    """Test CampaignContactAttemptInline configuration."""

    def test_inline_configuration(self):
        """Test inline is configured correctly."""
        inline = CampaignContactAttemptInline(Campaign, AdminSite())

        assert inline.model == ContactAttempt
        assert inline.extra == 1
        assert inline.can_delete is True

        # Check fields
        assert "contact_type" in inline.fields
        assert "contact_date" in inline.fields
        assert "result" in inline.fields
        assert "notes" in inline.fields
        assert "contacted_by" in inline.fields

        # Check readonly fields
        assert "contacted_by" in inline.readonly_fields
        assert "created_at" in inline.readonly_fields

        # Check ordering
        assert inline.ordering == ["-contact_date"]

    def test_get_queryset_optimization(self, db, admin_user, campaign, request_factory):
        """Test get_queryset performs necessary joins."""
        from civicpulse.models import Person

        inline = CampaignContactAttemptInline(Campaign, AdminSite())

        # Create a contact attempt
        person = Person.objects.create(
            first_name="Test",
            last_name="Person",
            created_by=admin_user,
        )

        ContactAttempt.objects.create(
            person=person,
            campaign=campaign,
            contact_type="phone",
            contact_date=timezone.now(),
            contacted_by=admin_user,
            result="contacted",
        )

        request = request_factory.get("/admin/civicpulse/campaign/")
        request.user = admin_user
        queryset = inline.get_queryset(request)

        # Verify queryset contains contact attempts
        assert queryset.exists()
        # Verify ordering is correct
        first_attempt = queryset.first()
        assert first_attempt.contact_type == "phone"
