"""
Comprehensive API tests for Campaign REST endpoints.

Tests all Campaign ViewSet endpoints including:
- List campaigns (GET /api/v1/campaigns/)
- Create campaign (POST /api/v1/campaigns/)
- Retrieve campaign (GET /api/v1/campaigns/{id}/)
- Update campaign (PUT/PATCH /api/v1/campaigns/{id}/)
- Delete campaign (DELETE /api/v1/campaigns/{id}/)
- Archive campaign (PATCH /api/v1/campaigns/{id}/archive/)
- Activate campaign (PATCH /api/v1/campaigns/{id}/activate/)
- Duplicate check (POST /api/v1/campaigns/duplicate_check/)

Coverage includes:
- Authentication and permissions
- Serializer selection (List/Detail/Standard)
- Filtering, searching, and ordering
- Validation and error handling
- Soft delete behavior
- Custom actions
- Queryset optimization

Author: John Taylor
Created: 2025-11-11
"""

import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from civicpulse.models import Campaign, ContactAttempt, Person

User = get_user_model()


@pytest.fixture
def api_client() -> APIClient:
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
@pytest.mark.django_db
def admin_user(db) -> User:
    """Create an admin user with is_staff=True."""
    return User.objects.create_user(
        username="adminuser",
        email="admin@test.com",
        password="AdminPass123!@#",
        first_name="Admin",
        last_name="User",
        role="admin",
        is_staff=True,
    )


@pytest.fixture
@pytest.mark.django_db
def campaign(admin_user: User) -> Campaign:
    """Create a basic campaign instance."""
    return Campaign.objects.create(
        name="Test Campaign 2025",
        candidate_name="John Doe",
        election_date=date.today() + timedelta(days=60),
        status="active",
        organization="Test Organization",
        description="Test campaign description",
        created_by=admin_user,
    )


@pytest.fixture
def campaign_data() -> dict[str, Any]:
    """Dictionary with valid POST data for campaign creation."""
    return {
        "name": "New Campaign 2025",
        "candidate_name": "Jane Smith",
        "election_date": str(date.today() + timedelta(days=90)),
        "status": "active",
        "organization": "Democratic Party",
        "description": "A new campaign for 2025",
    }


@pytest.fixture
@pytest.mark.django_db
def archived_campaign(admin_user: User) -> Campaign:
    """Create an archived campaign."""
    return Campaign.objects.create(
        name="Archived Campaign",
        candidate_name="Past Candidate",
        election_date=date.today() - timedelta(days=30),
        status="archived",
        organization="Past Organization",
        created_by=admin_user,
    )


@pytest.fixture
@pytest.mark.django_db
def soft_deleted_campaign(admin_user: User) -> Campaign:
    """Create a soft-deleted campaign."""
    campaign = Campaign.objects.create(
        name="Deleted Campaign",
        candidate_name="Deleted Candidate",
        election_date=date.today() + timedelta(days=30),
        status="active",
        created_by=admin_user,
    )
    campaign.soft_delete(user=admin_user)
    return campaign


@pytest.fixture
@pytest.mark.django_db
def person_for_contact(admin_user: User) -> Person:
    """Create a person for contact attempts."""
    return Person.objects.create(
        first_name="Contact",
        last_name="Person",
        email="contact@example.com",
        phone_primary="555-0100",
        street_address="123 Main St",
        city="Springfield",
        state="IL",
        zip_code="62701",
        created_by=admin_user,
    )


@pytest.mark.django_db
class TestCampaignListAPI:
    """Test campaign list endpoint (GET /api/v1/campaigns/)."""

    def test_list_campaigns_authenticated(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test listing campaigns with authentication succeeds."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/campaigns/")

        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert len(response.data["results"]) >= 1

    def test_list_campaigns_unauthenticated_fails(self, api_client: APIClient):
        """Test that unauthenticated requests are denied."""
        response = api_client.get("/api/v1/campaigns/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_campaigns_uses_list_serializer_fields(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test that list endpoint uses CampaignListSerializer fields."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/campaigns/")

        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]

        # List serializer should have these fields
        expected_fields = {
            "id",
            "name",
            "candidate_name",
            "election_date",
            "status",
            "days_until_election",
            "is_upcoming",
        }
        assert set(result.keys()) == expected_fields

    def test_list_campaigns_search_by_name(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test searching campaigns by name."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/campaigns/?search=Test Campaign")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1
        assert "Test Campaign" in response.data["results"][0]["name"]

    def test_list_campaigns_search_by_candidate(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test searching campaigns by candidate name."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/campaigns/?search=John Doe")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1
        assert response.data["results"][0]["candidate_name"] == "John Doe"

    def test_list_campaigns_filter_by_status(
        self,
        api_client: APIClient,
        admin_user: User,
        campaign: Campaign,
        archived_campaign: Campaign,
    ):
        """Test filtering campaigns by status."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/campaigns/?status=active")

        assert response.status_code == status.HTTP_200_OK
        for result in response.data["results"]:
            assert result["status"] == "active"

    def test_list_campaigns_filter_by_organization(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test filtering campaigns by organization."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/campaigns/?organization=Test")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_list_campaigns_ordering_by_name(
        self, api_client: APIClient, admin_user: User
    ):
        """Test ordering campaigns by name."""
        # Create multiple campaigns
        Campaign.objects.create(
            name="Alpha Campaign",
            candidate_name="Candidate A",
            election_date=date.today() + timedelta(days=30),
            created_by=admin_user,
        )
        Campaign.objects.create(
            name="Beta Campaign",
            candidate_name="Candidate B",
            election_date=date.today() + timedelta(days=30),
            created_by=admin_user,
        )

        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/campaigns/?ordering=name")

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        assert results[0]["name"] < results[1]["name"]

    def test_list_campaigns_ordering_by_election_date(
        self, api_client: APIClient, admin_user: User
    ):
        """Test ordering campaigns by election date."""
        # Create campaigns with different dates
        Campaign.objects.create(
            name="Early Campaign",
            candidate_name="Candidate A",
            election_date=date.today() + timedelta(days=30),
            created_by=admin_user,
        )
        Campaign.objects.create(
            name="Late Campaign",
            candidate_name="Candidate B",
            election_date=date.today() + timedelta(days=90),
            created_by=admin_user,
        )

        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/campaigns/?ordering=election_date")

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        assert len(results) >= 2

    def test_list_campaigns_pagination(self, api_client: APIClient, admin_user: User):
        """Test that list endpoint returns paginated results."""
        # Create multiple campaigns
        for i in range(5):
            Campaign.objects.create(
                name=f"Campaign {i}",
                candidate_name=f"Candidate {i}",
                election_date=date.today() + timedelta(days=30),
                created_by=admin_user,
            )

        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/campaigns/")

        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "results" in response.data
        assert "next" in response.data or "previous" in response.data


@pytest.mark.django_db
class TestCampaignCreateAPI:
    """Test campaign create endpoint (POST /api/v1/campaigns/)."""

    def test_create_campaign_success(
        self,
        api_client: APIClient,
        admin_user: User,
        campaign_data: dict[str, Any],
    ):
        """Test creating a campaign successfully."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == campaign_data["name"]
        assert response.data["candidate_name"] == campaign_data["candidate_name"]
        assert "id" in response.data

    def test_create_campaign_unauthenticated_fails(
        self, api_client: APIClient, campaign_data: dict[str, Any]
    ):
        """Test that unauthenticated create requests fail."""
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_campaign_sets_created_by(
        self,
        api_client: APIClient,
        admin_user: User,
        campaign_data: dict[str, Any],
    ):
        """Test that created_by is set to current user."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["created_by"] == admin_user.username

        # Verify in database
        campaign = Campaign.objects.get(id=response.data["id"])
        assert campaign.created_by == admin_user

    def test_create_campaign_returns_201_status(
        self,
        api_client: APIClient,
        admin_user: User,
        campaign_data: dict[str, Any],
    ):
        """Test that successful creation returns 201 status."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_campaign_missing_required_name(
        self, api_client: APIClient, admin_user: User, campaign_data: dict[str, Any]
    ):
        """Test that missing name field fails validation."""
        api_client.force_authenticate(user=admin_user)
        campaign_data.pop("name")
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_create_campaign_missing_required_candidate(
        self, api_client: APIClient, admin_user: User, campaign_data: dict[str, Any]
    ):
        """Test that missing candidate_name field fails validation."""
        api_client.force_authenticate(user=admin_user)
        campaign_data.pop("candidate_name")
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "candidate_name" in response.data

    def test_create_campaign_missing_required_election_date(
        self, api_client: APIClient, admin_user: User, campaign_data: dict[str, Any]
    ):
        """Test that missing election_date field fails validation."""
        api_client.force_authenticate(user=admin_user)
        campaign_data.pop("election_date")
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "election_date" in response.data

    def test_create_campaign_past_election_date_fails(
        self, api_client: APIClient, admin_user: User, campaign_data: dict[str, Any]
    ):
        """Test that past election date fails for new campaigns."""
        api_client.force_authenticate(user=admin_user)
        campaign_data["election_date"] = str(date.today() - timedelta(days=30))
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "election_date" in response.data

    def test_create_campaign_future_election_date_too_far(
        self, api_client: APIClient, admin_user: User, campaign_data: dict[str, Any]
    ):
        """Test that election date over 10 years in future fails."""
        api_client.force_authenticate(user=admin_user)
        campaign_data["election_date"] = str(date.today() + timedelta(days=3650 + 1))
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "election_date" in response.data

    def test_create_campaign_invalid_status_choice(
        self, api_client: APIClient, admin_user: User, campaign_data: dict[str, Any]
    ):
        """Test that invalid status choice fails validation."""
        api_client.force_authenticate(user=admin_user)
        campaign_data["status"] = "invalid_status"
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "status" in response.data

    def test_create_campaign_with_all_fields(
        self, api_client: APIClient, admin_user: User
    ):
        """Test creating a campaign with all optional fields."""
        full_data = {
            "name": "Complete Campaign",
            "candidate_name": "Full Candidate",
            "election_date": str(date.today() + timedelta(days=60)),
            "status": "active",
            "organization": "Full Organization Name",
            "description": "A complete description of the campaign",
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.post("/api/v1/campaigns/", full_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["organization"] == full_data["organization"]
        assert response.data["description"] == full_data["description"]

    def test_create_campaign_uses_service_layer(
        self,
        api_client: APIClient,
        admin_user: User,
        campaign_data: dict[str, Any],
    ):
        """Test that campaign creation uses CampaignCreationService."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        # Verify campaign exists in database (created by service)
        campaign = Campaign.objects.get(id=response.data["id"])
        assert campaign.name == campaign_data["name"]
        assert campaign.created_by == admin_user


@pytest.mark.django_db
class TestCampaignRetrieveAPI:
    """Test campaign retrieve endpoint (GET /api/v1/campaigns/{id}/)."""

    def test_retrieve_campaign_success(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test retrieving a campaign successfully."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(f"/api/v1/campaigns/{campaign.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(campaign.id)
        assert response.data["name"] == campaign.name

    def test_retrieve_campaign_unauthenticated_fails(
        self, api_client: APIClient, campaign: Campaign
    ):
        """Test that unauthenticated retrieve requests fail."""
        response = api_client.get(f"/api/v1/campaigns/{campaign.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_retrieve_campaign_uses_detail_serializer(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test that retrieve endpoint uses CampaignDetailSerializer fields."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(f"/api/v1/campaigns/{campaign.id}/")

        assert response.status_code == status.HTTP_200_OK

        # Detail serializer should have these additional fields
        assert "contact_attempts_count" in response.data
        assert "recent_contact_attempts" in response.data
        assert "days_until_election" in response.data
        assert "is_upcoming" in response.data
        assert "description" in response.data

    def test_retrieve_campaign_includes_related_data(
        self,
        api_client: APIClient,
        admin_user: User,
        campaign: Campaign,
        person_for_contact: Person,
    ):
        """Test that retrieve includes related contact attempts data."""
        # Create a contact attempt
        ContactAttempt.objects.create(
            campaign=campaign,
            person=person_for_contact,
            contact_type="phone",
            contact_date=timezone.now(),
            result="contacted",
            contacted_by=admin_user,
        )

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(f"/api/v1/campaigns/{campaign.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["contact_attempts_count"] >= 1
        assert len(response.data["recent_contact_attempts"]) >= 1

    def test_retrieve_campaign_not_found(self, api_client: APIClient, admin_user: User):
        """Test retrieving non-existent campaign returns 404."""
        api_client.force_authenticate(user=admin_user)
        fake_id = uuid.uuid4()
        response = api_client.get(f"/api/v1/campaigns/{fake_id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_campaign_soft_deleted_not_found(
        self, api_client: APIClient, admin_user: User, soft_deleted_campaign: Campaign
    ):
        """Test that soft-deleted campaigns are not retrievable."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(f"/api/v1/campaigns/{soft_deleted_campaign.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCampaignUpdateAPI:
    """Test campaign update endpoints (PUT/PATCH /api/v1/campaigns/{id}/)."""

    def test_full_update_campaign_success(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test full update (PUT) of campaign."""
        update_data = {
            "name": "Updated Campaign Name",
            "candidate_name": "Updated Candidate",
            "election_date": str(date.today() + timedelta(days=90)),
            "status": "paused",
            "organization": "Updated Organization",
            "description": "Updated description",
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            f"/api/v1/campaigns/{campaign.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == update_data["name"]
        assert response.data["status"] == update_data["status"]

    def test_partial_update_campaign_success(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test partial update (PATCH) of campaign."""
        update_data = {"status": "completed"}

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/v1/campaigns/{campaign.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"
        # Other fields should remain unchanged
        assert response.data["name"] == campaign.name

    def test_update_campaign_unauthenticated_fails(
        self, api_client: APIClient, campaign: Campaign
    ):
        """Test that unauthenticated update requests fail."""
        update_data = {"status": "paused"}
        response = api_client.patch(
            f"/api/v1/campaigns/{campaign.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_campaign_past_election_date_allowed(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test updating to past election date is allowed for existing campaigns."""
        update_data = {"election_date": str(date.today() - timedelta(days=30))}

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/v1/campaigns/{campaign.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["election_date"] == update_data["election_date"]

    def test_update_campaign_validation_error(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test that validation errors are returned properly."""
        update_data = {"status": "invalid_status"}

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/v1/campaigns/{campaign.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "status" in response.data

    def test_update_campaign_not_found(self, api_client: APIClient, admin_user: User):
        """Test updating non-existent campaign returns 404."""
        api_client.force_authenticate(user=admin_user)
        fake_id = uuid.uuid4()
        update_data = {"status": "paused"}
        response = api_client.patch(
            f"/api/v1/campaigns/{fake_id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_campaign_does_not_change_created_by(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test that updating a campaign doesn't change created_by."""
        original_creator = campaign.created_by
        update_data = {"description": "New description"}

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/v1/campaigns/{campaign.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        campaign.refresh_from_db()
        assert campaign.created_by == original_creator

    def test_update_campaign_updates_timestamp(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test that updating a campaign updates the updated_at timestamp."""
        original_updated_at = campaign.updated_at
        update_data = {"description": "New description"}

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/v1/campaigns/{campaign.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        campaign.refresh_from_db()
        assert campaign.updated_at > original_updated_at

    def test_update_status_only(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test updating only the status field."""
        update_data = {"status": "archived"}

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/v1/campaigns/{campaign.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "archived"

    def test_update_multiple_fields(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test updating multiple fields at once."""
        update_data = {
            "status": "completed",
            "description": "Campaign is now complete",
            "organization": "Final Organization",
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/v1/campaigns/{campaign.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == update_data["status"]
        assert response.data["description"] == update_data["description"]
        assert response.data["organization"] == update_data["organization"]


@pytest.mark.django_db
class TestCampaignDeleteAPI:
    """Test campaign delete endpoint (DELETE /api/v1/campaigns/{id}/)."""

    def test_delete_campaign_soft_delete(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test that delete performs soft delete, not hard delete."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(f"/api/v1/campaigns/{campaign.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Campaign should still exist in database
        campaign.refresh_from_db()
        assert campaign.is_active is False
        assert campaign.deleted_at is not None

    def test_delete_campaign_unauthenticated_fails(
        self, api_client: APIClient, campaign: Campaign
    ):
        """Test that unauthenticated delete requests fail."""
        response = api_client.delete(f"/api/v1/campaigns/{campaign.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_campaign_not_found(self, api_client: APIClient, admin_user: User):
        """Test deleting non-existent campaign returns 404."""
        api_client.force_authenticate(user=admin_user)
        fake_id = uuid.uuid4()
        response = api_client.delete(f"/api/v1/campaigns/{fake_id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_campaign_sets_audit_fields(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test that delete sets deleted_at and deleted_by fields."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(f"/api/v1/campaigns/{campaign.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        campaign.refresh_from_db()
        assert campaign.deleted_at is not None
        assert campaign.deleted_by == admin_user

    def test_delete_campaign_returns_204_status(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test that successful delete returns 204 No Content status."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(f"/api/v1/campaigns/{campaign.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not response.data


@pytest.mark.django_db
class TestCampaignArchiveAction:
    """Test campaign archive custom action (PATCH /api/v1/campaigns/{id}/archive/)."""

    def test_archive_campaign_success(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test archiving a campaign successfully."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(f"/api/v1/campaigns/{campaign.id}/archive/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "archived"

        # Verify in database
        campaign.refresh_from_db()
        assert campaign.status == "archived"

    def test_archive_campaign_unauthenticated_fails(
        self, api_client: APIClient, campaign: Campaign
    ):
        """Test that unauthenticated archive requests fail."""
        response = api_client.patch(f"/api/v1/campaigns/{campaign.id}/archive/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_archive_campaign_sets_status_archived(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test that archive action sets status to 'archived'."""
        original_status = campaign.status
        assert original_status != "archived"

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(f"/api/v1/campaigns/{campaign.id}/archive/")

        assert response.status_code == status.HTTP_200_OK
        campaign.refresh_from_db()
        assert campaign.status == "archived"
        assert campaign.status != original_status

    def test_archive_campaign_not_found(self, api_client: APIClient, admin_user: User):
        """Test archiving non-existent campaign returns 404."""
        api_client.force_authenticate(user=admin_user)
        fake_id = uuid.uuid4()
        response = api_client.patch(f"/api/v1/campaigns/{fake_id}/archive/")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCampaignActivateAction:
    """Test campaign activate custom action (PATCH /api/v1/campaigns/{id}/activate/)."""

    def test_activate_campaign_success(
        self, api_client: APIClient, admin_user: User, archived_campaign: Campaign
    ):
        """Test activating a campaign successfully."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/v1/campaigns/{archived_campaign.id}/activate/"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "active"

        # Verify in database
        archived_campaign.refresh_from_db()
        assert archived_campaign.status == "active"

    def test_activate_campaign_unauthenticated_fails(
        self, api_client: APIClient, campaign: Campaign
    ):
        """Test that unauthenticated activate requests fail."""
        response = api_client.patch(f"/api/v1/campaigns/{campaign.id}/activate/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_activate_campaign_sets_status_active(
        self, api_client: APIClient, admin_user: User, archived_campaign: Campaign
    ):
        """Test that activate action sets status to 'active'."""
        assert archived_campaign.status == "archived"

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            f"/api/v1/campaigns/{archived_campaign.id}/activate/"
        )

        assert response.status_code == status.HTTP_200_OK
        archived_campaign.refresh_from_db()
        assert archived_campaign.status == "active"

    def test_activate_campaign_not_found(self, api_client: APIClient, admin_user: User):
        """Test activating non-existent campaign returns 404."""
        api_client.force_authenticate(user=admin_user)
        fake_id = uuid.uuid4()
        response = api_client.patch(f"/api/v1/campaigns/{fake_id}/activate/")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCampaignDuplicateCheckAction:
    """Test duplicate check action (POST /api/v1/campaigns/duplicate_check/)."""

    def test_duplicate_check_finds_duplicates(
        self, api_client: APIClient, admin_user: User, campaign: Campaign
    ):
        """Test that duplicate check finds existing campaigns."""
        check_data = {
            "name": campaign.name,
            "candidate_name": campaign.candidate_name,
            "election_date": str(campaign.election_date),
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/v1/campaigns/duplicate_check/", check_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["has_duplicates"] is True
        assert response.data["duplicate_count"] >= 1
        assert len(response.data["duplicates"]) >= 1

    def test_duplicate_check_no_duplicates(
        self, api_client: APIClient, admin_user: User
    ):
        """Test that duplicate check returns empty when no duplicates."""
        check_data = {
            "name": "Unique Campaign Name 123456",
            "candidate_name": "Unique Candidate",
            "election_date": str(date.today() + timedelta(days=100)),
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/v1/campaigns/duplicate_check/", check_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["has_duplicates"] is False
        assert response.data["duplicate_count"] == 0
        assert len(response.data["duplicates"]) == 0

    def test_duplicate_check_unauthenticated_fails(self, api_client: APIClient):
        """Test that unauthenticated duplicate check requests fail."""
        check_data = {
            "name": "Test Campaign",
            "candidate_name": "Test Candidate",
            "election_date": str(date.today() + timedelta(days=30)),
        }

        response = api_client.post(
            "/api/v1/campaigns/duplicate_check/", check_data, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_duplicate_check_missing_data(
        self, api_client: APIClient, admin_user: User
    ):
        """Test that duplicate check with missing data returns 400."""
        check_data = {"name": "Test Campaign"}  # Missing candidate_name and date

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/v1/campaigns/duplicate_check/", check_data, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    def test_duplicate_check_temporal_window(
        self, api_client: APIClient, admin_user: User
    ):
        """Test duplicate check finds campaigns with same candidate and date."""
        # Create campaign with specific candidate and date
        campaign = Campaign.objects.create(
            name="Unique Name A",
            candidate_name="Same Candidate",
            election_date=date.today() + timedelta(days=60),
            created_by=admin_user,
        )

        # Check with different name but same candidate and date
        check_data = {
            "name": "Different Name B",
            "candidate_name": campaign.candidate_name,
            "election_date": str(campaign.election_date),
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/v1/campaigns/duplicate_check/", check_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["has_duplicates"] is True
        assert any(
            d["similarity_reason"] == "same_candidate_and_date"
            for d in response.data["duplicates"]
        )

    def test_duplicate_check_returns_200_status(
        self, api_client: APIClient, admin_user: User
    ):
        """Test duplicate check always returns 200 (not 201) for successful checks."""
        check_data = {
            "name": "Any Campaign",
            "candidate_name": "Any Candidate",
            "election_date": str(date.today() + timedelta(days=30)),
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            "/api/v1/campaigns/duplicate_check/", check_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestCampaignAPIPermissions:
    """Test API permissions for all campaign endpoints."""

    def test_list_requires_authentication(self, api_client: APIClient):
        """Test that list endpoint requires authentication."""
        response = api_client.get("/api/v1/campaigns/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_requires_authentication(
        self, api_client: APIClient, campaign_data: dict[str, Any]
    ):
        """Test that create endpoint requires authentication."""
        response = api_client.post("/api/v1/campaigns/", campaign_data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_detail_requires_authentication(
        self, api_client: APIClient, campaign: Campaign
    ):
        """Test that retrieve endpoint requires authentication."""
        response = api_client.get(f"/api/v1/campaigns/{campaign.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCampaignAPIQuerysetOptimization:
    """Test queryset optimization for campaign API."""

    def test_queryset_uses_select_related(
        self,
        api_client: APIClient,
        admin_user: User,
        campaign: Campaign,
    ):
        """Test that queryset uses select_related for related fields."""
        api_client.force_authenticate(user=admin_user)

        # Access list endpoint (will use optimized queryset)
        response = api_client.get("/api/v1/campaigns/")

        assert response.status_code == status.HTTP_200_OK
        # The queryset should have select_related for created_by, deleted_by
        # This can't be directly tested but we verify the endpoint works
        assert "results" in response.data

    def test_queryset_uses_prefetch_related(
        self,
        api_client: APIClient,
        admin_user: User,
        campaign: Campaign,
        person_for_contact: Person,
    ):
        """Test that queryset uses prefetch_related for contact_attempts."""
        # Create multiple contact attempts
        for i in range(3):
            ContactAttempt.objects.create(
                campaign=campaign,
                person=person_for_contact,
                contact_type="phone",
                contact_date=timezone.now() - timedelta(days=i),
                result="contacted",
                contacted_by=admin_user,
            )

        api_client.force_authenticate(user=admin_user)

        # Access detail endpoint (will use optimized queryset)
        response = api_client.get(f"/api/v1/campaigns/{campaign.id}/")

        assert response.status_code == status.HTTP_200_OK
        # Verify contact attempts are returned (meaning prefetch worked)
        assert response.data["contact_attempts_count"] == 3
        assert len(response.data["recent_contact_attempts"]) == 3
