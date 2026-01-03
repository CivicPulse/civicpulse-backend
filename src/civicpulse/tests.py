"""Tests for civicpulse application."""

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import (
    Address,
    ContactEffort,
    EffortAssignment,
    Election,
    ElectionVoter,
    Office,
    Person,
    PhoneNumber,
    VoterAddress,
    VoterPhoneNumber,
)


class AssignmentAddViewTests(TestCase):
    """Tests for the assignment_add view to ensure correct model usage."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client.login(username="testuser", password="password")

        # Create office and election
        self.office = Office.objects.create(name="Test Office")
        self.election = Election.objects.create(office=self.office, year=2026)

    def test_election_campaign_shows_election_voters(self):
        """Campaign linked to election should show ElectionVoter count, not Person."""
        # Create ElectionVoters with phone numbers
        for i in range(5):
            voter = ElectionVoter.objects.create(
                election=self.election,
                voter_id=f"V{i}",
                first_name=f"Test{i}",
                last_name="Voter",
            )
            VoterPhoneNumber.objects.create(voter=voter, number=f"555-000{i}")

        # Create campaign linked to election
        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=self.election, created_by=self.user
        )

        response = self.client.get(f"/campaigns/{campaign.pk}/assignments/add/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preview_count"], 5)
        self.assertTrue(response.context["uses_election_voters"])

    def test_election_campaign_excludes_already_assigned(self):
        """Preview count should exclude voters already assigned to campaign."""
        voters = []
        for i in range(5):
            voter = ElectionVoter.objects.create(
                election=self.election,
                voter_id=f"V{i}",
                first_name=f"Test{i}",
                last_name="Voter",
            )
            VoterPhoneNumber.objects.create(voter=voter, number=f"555-000{i}")
            voters.append(voter)

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=self.election, created_by=self.user
        )

        # Assign 2 voters
        EffortAssignment.objects.create(effort=campaign, election_voter=voters[0])
        EffortAssignment.objects.create(effort=campaign, election_voter=voters[1])

        response = self.client.get(f"/campaigns/{campaign.pk}/assignments/add/")
        self.assertEqual(response.context["preview_count"], 3)

    def test_election_campaign_filters_by_has_phone(self):
        """Only voters with phone numbers should be counted."""
        # Voter with phone
        voter1 = ElectionVoter.objects.create(
            election=self.election,
            voter_id="V1",
            first_name="With",
            last_name="Phone",
        )
        VoterPhoneNumber.objects.create(voter=voter1, number="555-0001")

        # Voter without phone
        ElectionVoter.objects.create(
            election=self.election,
            voter_id="V2",
            first_name="No",
            last_name="Phone",
        )

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=self.election, created_by=self.user
        )

        response = self.client.get(f"/campaigns/{campaign.pk}/assignments/add/")
        self.assertEqual(response.context["preview_count"], 1)

    def test_bulk_assign_creates_election_voter_assignments(self):
        """POST should create EffortAssignment with election_voter, not person."""
        voter = ElectionVoter.objects.create(
            election=self.election,
            voter_id="V1",
            first_name="Test",
            last_name="Voter",
        )
        VoterPhoneNumber.objects.create(voter=voter, number="555-0001")

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=self.election, created_by=self.user
        )

        self.client.post(
            f"/campaigns/{campaign.pk}/assignments/add/",
            {"has_phone": True, "limit": 100},
        )

        assignment = EffortAssignment.objects.first()
        self.assertIsNotNone(assignment)
        self.assertIsNone(assignment.person)
        self.assertEqual(assignment.election_voter, voter)

    def test_non_election_campaign_uses_person_model(self):
        """Campaign without election should query Person model."""
        # Create Person with phone number
        person = Person.objects.create(first_name="Test", last_name="Person")
        PhoneNumber.objects.create(person=person, number="555-0001")

        # Create campaign without election
        campaign = ContactEffort.objects.create(
            name="Non-Election Campaign", election=None, created_by=self.user
        )

        response = self.client.get(f"/campaigns/{campaign.pk}/assignments/add/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preview_count"], 1)
        self.assertFalse(response.context["uses_election_voters"])

    def test_non_election_campaign_bulk_assign_uses_person(self):
        """Non-election campaign POST should use person FK."""
        person = Person.objects.create(first_name="Test", last_name="Person")
        PhoneNumber.objects.create(person=person, number="555-0001")

        campaign = ContactEffort.objects.create(
            name="Non-Election Campaign", election=None, created_by=self.user
        )

        self.client.post(
            f"/campaigns/{campaign.pk}/assignments/add/",
            {"has_phone": True, "limit": 100},
        )

        assignment = EffortAssignment.objects.first()
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.person, person)
        self.assertIsNone(assignment.election_voter)

    def test_template_shows_voters_for_election_campaign(self):
        """Template should display 'voters' text for election-based campaigns."""
        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=self.election, created_by=self.user
        )

        response = self.client.get(f"/campaigns/{campaign.pk}/assignments/add/")
        content = response.content.decode()
        self.assertIn("Add Voters to Campaign", content)
        self.assertIn("voters with phone numbers", content)

    def test_template_shows_persons_for_non_election_campaign(self):
        """Template should display 'persons' text for non-election campaigns."""
        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=None, created_by=self.user
        )

        response = self.client.get(f"/campaigns/{campaign.pk}/assignments/add/")
        content = response.content.decode()
        self.assertIn("Add Persons to Campaign", content)
        self.assertIn("persons with phone numbers", content)


class CandidateDetailTests(TestCase):
    """Tests for candidate_detail view with null/missing person handling."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client.login(username="testuser", password="password")

        self.office = Office.objects.create(name="Test Office")
        self.election = Election.objects.create(office=self.office, year=2026)

    def test_candidate_detail_with_person(self):
        """Candidate with linked person shows contact info."""
        from .models import Candidate

        person = Person.objects.create(first_name="Jane", last_name="Doe")
        PhoneNumber.objects.create(person=person, number="555-1234", is_primary=True)

        candidate = Candidate.objects.create(
            person=person, election=self.election, party_affiliation="Independent"
        )

        response = self.client.get(f"/candidates/{candidate.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "555-1234")

    def test_candidate_detail_with_null_person(self):
        """Candidate without person record doesn't crash."""
        from .models import Candidate

        candidate = Candidate.objects.create(
            person=None, election=self.election, party_affiliation="Independent"
        )

        response = self.client.get(f"/candidates/{candidate.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No contact information")

    def test_candidate_set_null_on_person_delete(self):
        """Deleting person sets candidate.person to NULL instead of cascading delete."""
        from .models import Candidate

        person = Person.objects.create(first_name="John", last_name="Smith")
        candidate = Candidate.objects.create(
            person=person, election=self.election, party_affiliation="Independent"
        )
        candidate_pk = candidate.pk

        # Delete the person
        person.delete()

        # Candidate should still exist with person=NULL
        candidate.refresh_from_db()
        self.assertIsNotNone(Candidate.objects.filter(pk=candidate_pk).first())
        self.assertIsNone(candidate.person)


class CallingSessionTests(TestCase):
    """Tests for calling session views with dual-target support."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client.login(username="testuser", password="password")

        self.office = Office.objects.create(name="Test Office")
        self.election = Election.objects.create(office=self.office, year=2026)

    def test_calling_next_with_person_assignment(self):
        """Person-based assignments work in calling session."""
        person = Person.objects.create(first_name="Test", last_name="Person")
        PhoneNumber.objects.create(person=person, number="555-1111", is_primary=True)

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=None, created_by=self.user
        )
        EffortAssignment.objects.create(effort=campaign, person=person)

        response = self.client.get(f"/drives/{campaign.pk}/call/next/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Person")
        self.assertContains(response, "555-1111")

    def test_calling_next_with_election_voter_assignment(self):
        """ElectionVoter-based assignments work in calling session."""
        voter = ElectionVoter.objects.create(
            election=self.election,
            voter_id="V123",
            first_name="Election",
            last_name="Voter",
        )
        VoterPhoneNumber.objects.create(voter=voter, number="555-2222", is_primary=True)

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=self.election, created_by=self.user
        )
        EffortAssignment.objects.create(effort=campaign, election_voter=voter)

        response = self.client.get(f"/drives/{campaign.pk}/call/next/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Election Voter")
        self.assertContains(response, "555-2222")

    def test_calling_log_creates_person_contact_attempt(self):
        """ContactAttempt links to Person for person-based assignments."""
        from .models import ContactAttempt

        person = Person.objects.create(first_name="Test", last_name="Person")
        PhoneNumber.objects.create(person=person, number="555-1111", is_primary=True)

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=None, created_by=self.user
        )
        assignment = EffortAssignment.objects.create(effort=campaign, person=person)

        # First get next to lock the assignment
        self.client.get(f"/drives/{campaign.pk}/call/next/")

        # Log outcome
        response = self.client.post(
            f"/drives/{campaign.pk}/call/log/",
            {
                "assignment_id": str(assignment.pk),
                "outcome": "spoke_with",
                "phone_number_used": "555-1111",
                "contact_type": "call",
            },
        )
        self.assertEqual(response.status_code, 200)

        # Verify contact attempt was created with person
        attempt = ContactAttempt.objects.first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.person, person)
        self.assertIsNone(attempt.election_voter)

    def test_calling_log_creates_election_voter_contact_attempt(self):
        """ContactAttempt links to ElectionVoter for voter-based assignments."""
        from .models import ContactAttempt

        voter = ElectionVoter.objects.create(
            election=self.election,
            voter_id="V123",
            first_name="Election",
            last_name="Voter",
        )
        VoterPhoneNumber.objects.create(voter=voter, number="555-2222", is_primary=True)

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=self.election, created_by=self.user
        )
        assignment = EffortAssignment.objects.create(effort=campaign, election_voter=voter)

        # First get next to lock the assignment
        self.client.get(f"/drives/{campaign.pk}/call/next/")

        # Log outcome
        response = self.client.post(
            f"/drives/{campaign.pk}/call/log/",
            {
                "assignment_id": str(assignment.pk),
                "outcome": "spoke_with",
                "phone_number_used": "555-2222",
                "contact_type": "call",
            },
        )
        self.assertEqual(response.status_code, 200)

        # Verify contact attempt was created with election_voter
        attempt = ContactAttempt.objects.first()
        self.assertIsNotNone(attempt)
        self.assertIsNone(attempt.person)
        self.assertEqual(attempt.election_voter, voter)


class KnockingSessionTests(TestCase):
    """Tests for door knocking session views with dual-target support."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client.login(username="testuser", password="password")

        self.office = Office.objects.create(name="Test Office")
        self.election = Election.objects.create(office=self.office, year=2026)

    def test_knocking_next_with_person_assignment(self):
        """Person-based assignments work in knocking session."""
        from .models import Address

        person = Person.objects.create(first_name="Test", last_name="Person")
        Address.objects.create(
            person=person,
            street_address="123 Main St",
            city="Atlanta",
            state="GA",
            zip_code="30303",
            is_primary=True,
        )

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=None, created_by=self.user
        )
        EffortAssignment.objects.create(effort=campaign, person=person)

        # Set session location
        session = self.client.session
        session["knocker_lat"] = 33.749
        session["knocker_lon"] = -84.388
        session.save()

        response = self.client.get(f"/drives/{campaign.pk}/knock/next/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Person")
        self.assertContains(response, "123 Main St")

    def test_knocking_next_with_election_voter_assignment(self):
        """ElectionVoter-based assignments work in knocking session."""
        from .models import VoterAddress

        voter = ElectionVoter.objects.create(
            election=self.election,
            voter_id="V123",
            first_name="Election",
            last_name="Voter",
        )
        VoterAddress.objects.create(
            voter=voter,
            street_address="456 Oak Ave",
            city="Atlanta",
            state="GA",
            zip_code="30303",
            is_primary=True,
        )

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=self.election, created_by=self.user
        )
        EffortAssignment.objects.create(effort=campaign, election_voter=voter)

        # Set session location
        session = self.client.session
        session["knocker_lat"] = 33.749
        session["knocker_lon"] = -84.388
        session.save()

        response = self.client.get(f"/drives/{campaign.pk}/knock/next/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Election Voter")
        self.assertContains(response, "456 Oak Ave")

    def test_knocking_log_sets_voter_address_visited(self):
        """voter_address_visited populated for ElectionVoter door knocks."""
        from .models import ContactAttempt, VoterAddress

        voter = ElectionVoter.objects.create(
            election=self.election,
            voter_id="V123",
            first_name="Election",
            last_name="Voter",
        )
        address = VoterAddress.objects.create(
            voter=voter,
            street_address="456 Oak Ave",
            city="Atlanta",
            state="GA",
            zip_code="30303",
            is_primary=True,
        )

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=self.election, created_by=self.user
        )
        assignment = EffortAssignment.objects.create(effort=campaign, election_voter=voter)

        # Set session location and get next to lock
        session = self.client.session
        session["knocker_lat"] = 33.749
        session["knocker_lon"] = -84.388
        session.save()
        self.client.get(f"/drives/{campaign.pk}/knock/next/")

        # Log outcome
        response = self.client.post(
            f"/drives/{campaign.pk}/knock/log/",
            {
                "assignment_id": str(assignment.pk),
                "outcome": "spoke_at_door",
                "address_visited": str(address.pk),
            },
        )
        self.assertEqual(response.status_code, 200)

        # Verify voter_address_visited was set
        attempt = ContactAttempt.objects.first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.election_voter, voter)
        self.assertEqual(attempt.voter_address_visited, address)


class AssignmentListTests(TestCase):
    """Tests for assignment_list view with dual-target display."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.client.login(username="testuser", password="password")

        self.office = Office.objects.create(name="Test Office")
        self.election = Election.objects.create(office=self.office, year=2026)

    def test_assignment_list_shows_person_assignments(self):
        """Person assignments display name correctly."""
        person = Person.objects.create(first_name="John", last_name="Doe")

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=None, created_by=self.user
        )
        EffortAssignment.objects.create(effort=campaign, person=person)

        response = self.client.get(f"/drives/{campaign.pk}/assignments/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John Doe")

    def test_assignment_list_shows_election_voter_assignments(self):
        """ElectionVoter assignments display name correctly."""
        voter = ElectionVoter.objects.create(
            election=self.election,
            voter_id="V123",
            first_name="Jane",
            last_name="Smith",
        )

        campaign = ContactEffort.objects.create(
            name="Test Campaign", election=self.election, created_by=self.user
        )
        EffortAssignment.objects.create(effort=campaign, election_voter=voter)

        response = self.client.get(f"/drives/{campaign.pk}/assignments/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jane Smith")


class GetAssignmentTargetHelperTests(TestCase):
    """Tests for the get_assignment_target_with_details helper function."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user("testuser", "test@test.com", "password")
        self.office = Office.objects.create(name="Test Office")
        self.election = Election.objects.create(office=self.office, year=2026)

    def test_helper_returns_person_target(self):
        """Helper returns Person and 'person' type for person assignments."""
        from .views import get_assignment_target_with_details

        person = Person.objects.create(first_name="Test", last_name="Person")
        campaign = ContactEffort.objects.create(
            name="Test", election=None, created_by=self.user
        )
        assignment = EffortAssignment.objects.create(effort=campaign, person=person)

        target, target_type = get_assignment_target_with_details(assignment, campaign)
        self.assertEqual(target, person)
        self.assertEqual(target_type, "person")

    def test_helper_returns_election_voter_target(self):
        """Helper returns ElectionVoter and 'election_voter' type for voter assignments."""
        from .views import get_assignment_target_with_details

        voter = ElectionVoter.objects.create(
            election=self.election,
            voter_id="V123",
            first_name="Test",
            last_name="Voter",
        )
        campaign = ContactEffort.objects.create(
            name="Test", election=self.election, created_by=self.user
        )
        assignment = EffortAssignment.objects.create(effort=campaign, election_voter=voter)

        target, target_type = get_assignment_target_with_details(assignment, campaign)
        self.assertEqual(target, voter)
        self.assertEqual(target_type, "election_voter")

    def test_helper_returns_none_for_invalid_assignment(self):
        """Helper returns (None, None) when target doesn't exist."""
        from .views import get_assignment_target_with_details

        campaign = ContactEffort.objects.create(
            name="Test", election=None, created_by=self.user
        )
        # Create assignment with person_id that doesn't exist
        assignment = EffortAssignment(effort=campaign, person_id=99999)

        target, target_type = get_assignment_target_with_details(assignment, campaign)
        self.assertIsNone(target)
        self.assertIsNone(target_type)
