"""
Tests for voter/person search functionality.

This module tests the search views, API endpoints, and model search methods
for the CivicPulse voter search feature.
"""

import json
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from civicpulse.models import Person, VoterRecord

User = get_user_model()


@pytest.fixture
def search_user(db):
    """Create a user for search tests."""
    return User.objects.create_user(
        username="searchuser", email="search@test.com", password="testpass123"
    )


@pytest.fixture
def sample_voters(db):
    """Create sample voter data for search testing."""
    voters = []

    # Create voter 1: High priority Democrat in NY
    person1 = Person.objects.create(
        first_name="John",
        last_name="Smith",
        email="john.smith@example.com",
        phone_primary="555-0101",
        street_address="123 Main St",
        city="New York",
        state="NY",
        zip_code="10001",
    )
    VoterRecord.objects.create(
        person=person1,
        voter_id="NY12345",
        registration_status="active",
        party_affiliation="democrat",
        voter_score=85,
        precinct="P001",
        ward="W01",
    )
    voters.append(person1)

    # Create voter 2: Medium priority Republican in NY
    person2 = Person.objects.create(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone_primary="555-0102",
        street_address="456 Oak Ave",
        city="Buffalo",
        state="NY",
        zip_code="14201",
    )
    VoterRecord.objects.create(
        person=person2,
        voter_id="NY67890",
        registration_status="active",
        party_affiliation="republican",
        voter_score=55,
        precinct="P002",
        ward="W02",
    )
    voters.append(person2)

    # Create voter 3: Low priority Independent in CA
    person3 = Person.objects.create(
        first_name="Bob",
        last_name="Johnson",
        email="bob.johnson@example.com",
        phone_primary="555-0103",
        street_address="789 Pine Rd",
        city="Los Angeles",
        state="CA",
        zip_code="90001",
    )
    VoterRecord.objects.create(
        person=person3,
        voter_id="CA11111",
        registration_status="active",
        party_affiliation="independent",
        voter_score=25,
        precinct="P003",
        ward="W03",
    )
    voters.append(person3)

    # Create voter 4: Inactive voter in NY
    person4 = Person.objects.create(
        first_name="Alice",
        last_name="Williams",
        email="alice.williams@example.com",
        phone_primary="555-0104",
        street_address="321 Elm St",
        city="New York",
        state="NY",
        zip_code="10002",
    )
    VoterRecord.objects.create(
        person=person4,
        voter_id="NY22222",
        registration_status="inactive",
        party_affiliation="democrat",
        voter_score=70,
        precinct="P001",
        ward="W01",
    )
    voters.append(person4)

    # Create person without voter record
    person5 = Person.objects.create(
        first_name="Charlie",
        last_name="Brown",
        email="charlie.brown@example.com",
        phone_primary="555-0105",
        street_address="555 Maple Dr",
        city="New York",
        state="NY",
        zip_code="10003",
    )
    voters.append(person5)

    return voters


class TestPersonManagerSearch:
    """Test PersonManager search methods."""

    @pytest.mark.django_db
    def test_advanced_search_by_name(self, sample_voters):
        """Test advanced search filters by name."""
        results = Person.objects.advanced_search(search_query="John")
        assert results.count() == 2  # John Smith and Bob Johnson
        assert "John" in results.first().first_name or "John" in results.first().last_name

    @pytest.mark.django_db
    def test_advanced_search_by_email(self, sample_voters):
        """Test advanced search filters by email."""
        results = Person.objects.advanced_search(search_query="jane.doe")
        assert results.count() == 1
        assert results.first().email == "jane.doe@example.com"

    @pytest.mark.django_db
    def test_advanced_search_by_phone(self, sample_voters):
        """Test advanced search filters by phone number."""
        results = Person.objects.advanced_search(search_query="555-0103")
        assert results.count() == 1
        assert results.first().phone_primary == "555-0103"

    @pytest.mark.django_db
    def test_advanced_search_by_voter_id(self, sample_voters):
        """Test advanced search filters by voter ID."""
        results = Person.objects.advanced_search(search_query="NY12345")
        assert results.count() == 1
        assert results.first().voter_record.voter_id == "NY12345"

    @pytest.mark.django_db
    def test_advanced_search_by_state(self, sample_voters):
        """Test advanced search filters by state."""
        results = Person.objects.advanced_search(state="NY")
        assert results.count() == 4
        for person in results:
            assert person.state == "NY"

    @pytest.mark.django_db
    def test_advanced_search_by_city(self, sample_voters):
        """Test advanced search filters by city."""
        results = Person.objects.advanced_search(city="New York")
        assert results.count() == 3
        for person in results:
            assert person.city == "New York"

    @pytest.mark.django_db
    def test_advanced_search_by_zip_code(self, sample_voters):
        """Test advanced search filters by ZIP code."""
        results = Person.objects.advanced_search(zip_code="10001")
        assert results.count() == 1
        assert results.first().zip_code == "10001"

    @pytest.mark.django_db
    def test_advanced_search_by_voter_status(self, sample_voters):
        """Test advanced search filters by voter registration status."""
        results = Person.objects.advanced_search(voter_status="active")
        assert results.count() == 3
        for person in results:
            assert person.voter_record.registration_status == "active"

    @pytest.mark.django_db
    def test_advanced_search_by_party(self, sample_voters):
        """Test advanced search filters by party affiliation."""
        results = Person.objects.advanced_search(party_affiliation="democrat")
        assert results.count() == 2
        for person in results:
            assert person.voter_record.party_affiliation == "democrat"

    @pytest.mark.django_db
    def test_advanced_search_by_voter_score_range(self, sample_voters):
        """Test advanced search filters by voter score range."""
        results = Person.objects.advanced_search(min_voter_score=50, max_voter_score=80)
        assert results.count() == 2
        for person in results:
            assert 50 <= person.voter_record.voter_score <= 80

    @pytest.mark.django_db
    def test_advanced_search_by_precinct(self, sample_voters):
        """Test advanced search filters by precinct."""
        results = Person.objects.advanced_search(precinct="P001")
        assert results.count() == 2
        for person in results:
            assert person.voter_record.precinct == "P001"

    @pytest.mark.django_db
    def test_advanced_search_by_ward(self, sample_voters):
        """Test advanced search filters by ward."""
        results = Person.objects.advanced_search(ward="W01")
        assert results.count() == 2
        for person in results:
            assert person.voter_record.ward == "W01"

    @pytest.mark.django_db
    def test_advanced_search_combined_filters(self, sample_voters):
        """Test advanced search with multiple filters combined."""
        results = Person.objects.advanced_search(
            state="NY",
            party_affiliation="democrat",
            voter_status="active",
            min_voter_score=80,
        )
        assert results.count() == 1
        person = results.first()
        assert person.state == "NY"
        assert person.voter_record.party_affiliation == "democrat"
        assert person.voter_record.registration_status == "active"
        assert person.voter_record.voter_score >= 80

    @pytest.mark.django_db
    def test_advanced_search_no_results(self, sample_voters):
        """Test advanced search returns empty queryset when no matches."""
        results = Person.objects.advanced_search(search_query="NonExistent")
        assert results.count() == 0

    @pytest.mark.django_db
    def test_by_voter_status_method(self, sample_voters):
        """Test by_voter_status helper method."""
        results = Person.objects.by_voter_status("active")
        assert results.count() == 3

    @pytest.mark.django_db
    def test_by_party_method(self, sample_voters):
        """Test by_party helper method."""
        results = Person.objects.by_party("republican")
        assert results.count() == 1
        assert results.first().voter_record.party_affiliation == "republican"

    @pytest.mark.django_db
    def test_by_voter_score_range_method(self, sample_voters):
        """Test by_voter_score_range helper method."""
        results = Person.objects.by_voter_score_range(min_score=70)
        assert results.count() == 2
        for person in results:
            assert person.voter_record.voter_score >= 70

    @pytest.mark.django_db
    def test_high_priority_voters_method(self, sample_voters):
        """Test high_priority_voters helper method."""
        results = Person.objects.high_priority_voters()
        assert results.count() == 2  # Scores >= 70
        for person in results:
            assert person.voter_record.voter_score >= 70


class TestPersonSearchView:
    """Test PersonSearchView template view."""

    @pytest.mark.django_db
    def test_search_view_requires_login(self, client: Client):
        """Test that search view requires authentication."""
        url = reverse("civicpulse:person_search")
        response = client.get(url)
        assert response.status_code == 302  # Redirect to login
        assert "/login/" in response.url

    @pytest.mark.django_db
    def test_search_view_loads_for_authenticated_user(
        self, client: Client, search_user
    ):
        """Test that search view loads for authenticated users."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search")
        response = client.get(url)
        assert response.status_code == 200
        assert b"Voter Search" in response.content

    @pytest.mark.django_db
    def test_search_view_displays_results(
        self, client: Client, search_user, sample_voters
    ):
        """Test that search view displays search results."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search")
        response = client.get(url, {"q": "John"})
        assert response.status_code == 200
        assert b"John" in response.content
        assert b"Smith" in response.content

    @pytest.mark.django_db
    def test_search_view_pagination(self, client: Client, search_user, sample_voters):
        """Test that search view paginates results."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search")
        response = client.get(url)
        assert response.status_code == 200
        # Check pagination context
        assert "persons" in response.context
        assert hasattr(response.context["persons"], "paginator")

    @pytest.mark.django_db
    def test_search_view_filtering(self, client: Client, search_user, sample_voters):
        """Test that search view applies filters correctly."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search")
        response = client.get(url, {"state": "NY", "party": "democrat"})
        assert response.status_code == 200
        # Verify filters are in context
        assert response.context["filters"]["state"] == "NY"
        assert response.context["filters"]["party"] == "democrat"

    @pytest.mark.django_db
    def test_search_view_sorting(self, client: Client, search_user, sample_voters):
        """Test that search view applies sorting correctly."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search")
        response = client.get(url, {"sort": "voter_score"})
        assert response.status_code == 200
        assert response.context["sort_by"] == "voter_score"


class TestPersonSearchAPIView:
    """Test PersonSearchAPIView JSON API endpoint."""

    @pytest.mark.django_db
    def test_api_search_requires_login(self, client: Client):
        """Test that API search requires authentication."""
        url = reverse("civicpulse:person_search_api")
        response = client.get(url)
        assert response.status_code == 302  # Redirect to login

    @pytest.mark.django_db
    def test_api_search_returns_json(self, client: Client, search_user, sample_voters):
        """Test that API search returns JSON response."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search_api")
        response = client.get(url, {"q": "John"})
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

    @pytest.mark.django_db
    def test_api_search_response_structure(
        self, client: Client, search_user, sample_voters
    ):
        """Test that API search response has correct structure."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search_api")
        response = client.get(url, {"q": "John"})
        data = json.loads(response.content)

        assert "results" in data
        assert "total" in data
        assert "page" in data
        assert "num_pages" in data
        assert "has_next" in data
        assert "has_previous" in data

    @pytest.mark.django_db
    def test_api_search_filters_by_query(
        self, client: Client, search_user, sample_voters
    ):
        """Test that API search filters by search query."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search_api")
        response = client.get(url, {"q": "John Smith"})
        data = json.loads(response.content)

        assert data["total"] >= 1
        assert any("John" in r["first_name"] for r in data["results"])

    @pytest.mark.django_db
    def test_api_search_filters_by_state(
        self, client: Client, search_user, sample_voters
    ):
        """Test that API search filters by state."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search_api")
        response = client.get(url, {"state": "NY"})
        data = json.loads(response.content)

        assert data["total"] == 4
        for result in data["results"]:
            assert result["state"] == "NY"

    @pytest.mark.django_db
    def test_api_search_includes_voter_data(
        self, client: Client, search_user, sample_voters
    ):
        """Test that API search includes voter record data."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search_api")
        response = client.get(url, {"q": "John Smith"})
        data = json.loads(response.content)

        # Find John Smith in results
        john_smith = next(
            (r for r in data["results"] if r["first_name"] == "John"), None
        )
        assert john_smith is not None
        assert "voter" in john_smith
        assert "voter_id" in john_smith["voter"]
        assert "voter_score" in john_smith["voter"]

    @pytest.mark.django_db
    def test_api_search_pagination(self, client: Client, search_user, sample_voters):
        """Test that API search supports pagination."""
        client.force_login(search_user)
        url = reverse("civicpulse:person_search_api")
        response = client.get(url, {"page": "1", "page_size": "2"})
        data = json.loads(response.content)

        assert len(data["results"]) <= 2
        assert data["page"] == 1


class TestQuickSearchAPIView:
    """Test QuickSearchAPIView for autocomplete."""

    @pytest.mark.django_db
    def test_quick_search_requires_login(self, client: Client):
        """Test that quick search requires authentication."""
        url = reverse("civicpulse:quick_search_api")
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_quick_search_returns_json(
        self, client: Client, search_user, sample_voters
    ):
        """Test that quick search returns JSON response."""
        client.force_login(search_user)
        url = reverse("civicpulse:quick_search_api")
        response = client.get(url, {"q": "John"})
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

    @pytest.mark.django_db
    def test_quick_search_limits_results(
        self, client: Client, search_user, sample_voters
    ):
        """Test that quick search limits number of results."""
        client.force_login(search_user)
        url = reverse("civicpulse:quick_search_api")
        response = client.get(url, {"q": "o", "limit": "2"})
        data = json.loads(response.content)

        assert len(data["results"]) <= 2

    @pytest.mark.django_db
    def test_quick_search_requires_minimum_query_length(
        self, client: Client, search_user
    ):
        """Test that quick search requires at least 2 characters."""
        client.force_login(search_user)
        url = reverse("civicpulse:quick_search_api")
        response = client.get(url, {"q": "J"})
        data = json.loads(response.content)

        assert data["results"] == []


class TestSearchStatsAPIView:
    """Test SearchStatsAPIView for statistics."""

    @pytest.mark.django_db
    def test_stats_api_requires_login(self, client: Client):
        """Test that stats API requires authentication."""
        url = reverse("civicpulse:search_stats_api")
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_stats_api_returns_json(self, client: Client, search_user, sample_voters):
        """Test that stats API returns JSON response."""
        client.force_login(search_user)
        url = reverse("civicpulse:search_stats_api")
        response = client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

    @pytest.mark.django_db
    def test_stats_api_response_structure(
        self, client: Client, search_user, sample_voters
    ):
        """Test that stats API response has correct structure."""
        client.force_login(search_user)
        url = reverse("civicpulse:search_stats_api")
        response = client.get(url)
        data = json.loads(response.content)

        assert "totals" in data
        assert "registration_status" in data
        assert "party_affiliation" in data
        assert "states" in data
        assert "priority" in data

    @pytest.mark.django_db
    def test_stats_api_totals(self, client: Client, search_user, sample_voters):
        """Test that stats API returns correct totals."""
        client.force_login(search_user)
        url = reverse("civicpulse:search_stats_api")
        response = client.get(url)
        data = json.loads(response.content)

        assert data["totals"]["persons"] == 5
        assert data["totals"]["voters"] == 4
        assert data["totals"]["non_voters"] == 1


class TestExportSearchResults:
    """Test CSV export functionality."""

    @pytest.mark.django_db
    def test_export_requires_login(self, client: Client):
        """Test that export requires authentication."""
        url = reverse("civicpulse:search_export")
        response = client.get(url)
        assert response.status_code == 302

    @pytest.mark.django_db
    def test_export_returns_csv(self, client: Client, search_user, sample_voters):
        """Test that export returns CSV file."""
        client.force_login(search_user)
        url = reverse("civicpulse:search_export")
        response = client.get(url, {"state": "NY"})
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert "attachment" in response["Content-Disposition"]

    @pytest.mark.django_db
    def test_export_includes_headers(self, client: Client, search_user, sample_voters):
        """Test that export CSV includes proper headers."""
        client.force_login(search_user)
        url = reverse("civicpulse:search_export")
        response = client.get(url)
        content = response.content.decode("utf-8")

        assert "First Name" in content
        assert "Last Name" in content
        assert "Email" in content
        assert "Voter ID" in content
        assert "Voter Score" in content

    @pytest.mark.django_db
    def test_export_includes_data(self, client: Client, search_user, sample_voters):
        """Test that export CSV includes actual data."""
        client.force_login(search_user)
        url = reverse("civicpulse:search_export")
        response = client.get(url, {"q": "John Smith"})
        content = response.content.decode("utf-8")

        assert "John" in content
        assert "Smith" in content
        assert "john.smith@example.com" in content

    @pytest.mark.django_db
    def test_export_applies_filters(self, client: Client, search_user, sample_voters):
        """Test that export applies search filters."""
        client.force_login(search_user)
        url = reverse("civicpulse:search_export")
        response = client.get(url, {"state": "CA"})
        content = response.content.decode("utf-8")

        # Should only include CA voters
        assert "Bob" in content
        assert "Johnson" in content
        # Should not include NY voters
        assert "John" not in content or "Smith" not in content


class TestSearchPerformance:
    """Test search performance with larger datasets."""

    @pytest.mark.django_db
    def test_search_performance_with_many_records(self, client: Client, search_user):
        """Test search performance with 100+ records."""
        # Create 100 test persons
        persons = []
        for i in range(100):
            person = Person.objects.create(
                first_name=f"Test{i}",
                last_name=f"User{i}",
                email=f"test{i}@example.com",
                city="Test City",
                state="NY",
                zip_code=f"{10000 + i}",
            )
            VoterRecord.objects.create(
                person=person,
                voter_id=f"NY{10000 + i}",
                registration_status="active",
                party_affiliation="democrat",
                voter_score=50 + (i % 50),
            )
            persons.append(person)

        # Test that search completes successfully
        client.force_login(search_user)
        url = reverse("civicpulse:person_search")
        response = client.get(url, {"state": "NY"})
        assert response.status_code == 200

        # Test pagination works
        assert "persons" in response.context
        paginator = response.context["persons"].paginator
        assert paginator.count >= 100

    @pytest.mark.django_db
    def test_api_search_performance(self, client: Client, search_user):
        """Test API search performance with pagination."""
        # Create 50 test persons for API test
        for i in range(50):
            person = Person.objects.create(
                first_name=f"API{i}",
                last_name=f"Test{i}",
                email=f"api{i}@example.com",
                city="API City",
                state="TX",
                zip_code=f"{75000 + i}",
            )
            VoterRecord.objects.create(
                person=person,
                voter_id=f"TX{20000 + i}",
                registration_status="active",
                party_affiliation="republican",
                voter_score=30 + (i % 70),
            )

        client.force_login(search_user)
        url = reverse("civicpulse:person_search_api")
        response = client.get(url, {"state": "TX", "page_size": "25"})
        data = json.loads(response.content)

        assert response.status_code == 200
        assert len(data["results"]) == 25
        assert data["total"] >= 50
        assert data["has_next"] is True
