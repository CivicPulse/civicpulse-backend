"""Tests for civicpulse application."""

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import (
    ContactEffort,
    EffortAssignment,
    Election,
    ElectionVoter,
    Office,
    Person,
    PhoneNumber,
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
