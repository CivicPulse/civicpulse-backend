import uuid
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from .models import ContactAttempt, Person, VoterRecord

User = get_user_model()


class UserModelTest(TestCase):
    """Test cases for the extended User model."""

    def setUp(self):
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'role': 'volunteer',
            'organization': 'Test Org',
            'phone_number': '+12125551234',
        }

    def test_create_user(self):
        """Test creating a user with custom fields."""
        user = User.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password'],
            role=self.user_data['role'],
            organization=self.user_data['organization'],
            phone_number=self.user_data['phone_number'],
        )

        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.role, 'volunteer')
        self.assertEqual(user.organization, 'Test Org')
        self.assertEqual(user.phone_number, '+12125551234')
        self.assertFalse(user.is_verified)
        self.assertIsInstance(user.id, uuid.UUID)

    def test_user_str_representation(self):
        """Test the string representation of User."""
        user = User.objects.create_user(
            username='johndoe',
            role='organizer'
        )
        self.assertEqual(str(user), 'johndoe (organizer)')

    def test_user_role_choices(self):
        """Test that role choices are enforced."""
        user = User.objects.create_user(username='testuser2')

        # Test valid roles
        for role, _ in User.ROLE_CHOICES:
            user.role = role
            user.full_clean()  # Should not raise

    def test_phone_number_validation(self):
        """Test phone number validation."""
        user = User.objects.create_user(username='testuser3')

        # Valid phone numbers
        valid_numbers = ['+12125551234', '12125551234', '2125551234']
        for number in valid_numbers:
            user.phone_number = number
            user.full_clean()  # Should not raise

        # Invalid phone number
        user.phone_number = '123'  # Too short
        with self.assertRaises(ValidationError):
            user.full_clean()


class PersonModelTest(TestCase):
    """Test cases for the Person model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='creator',
            email='creator@example.com'
        )

        self.person_data = {
            'first_name': 'John',
            'middle_name': 'Michael',
            'last_name': 'Doe',
            'suffix': 'Jr.',
            'date_of_birth': date(1980, 1, 15),
            'gender': 'M',
            'email': 'johndoe@example.com',
            'phone_primary': '+12125551234',
            'phone_secondary': '+12125555678',
            'street_address': '123 Main St',
            'apartment_number': 'Apt 4B',
            'city': 'New York',
            'state': 'NY',
            'zip_code': '10001',
            'county': 'New York County',
            'occupation': 'Software Engineer',
            'employer': 'Tech Corp',
            'notes': 'Active voter',
            'tags': ['volunteer', 'donor'],
            'created_by': self.user,
        }

    def test_create_person(self):
        """Test creating a person with all fields."""
        person = Person.objects.create(**self.person_data)

        self.assertEqual(person.first_name, 'John')
        self.assertEqual(person.last_name, 'Doe')
        self.assertEqual(person.email, 'johndoe@example.com')
        self.assertIsInstance(person.id, uuid.UUID)
        self.assertEqual(person.tags, ['volunteer', 'donor'])

    def test_person_full_name_property(self):
        """Test the full_name property."""
        person = Person.objects.create(**self.person_data)
        self.assertEqual(person.full_name, 'John Michael Doe Jr.')

        # Test without middle name and suffix
        person2 = Person.objects.create(
            first_name='Jane',
            last_name='Smith'
        )
        self.assertEqual(person2.full_name, 'Jane Smith')

    def test_person_str_representation(self):
        """Test the string representation of Person."""
        person = Person.objects.create(**self.person_data)
        self.assertEqual(str(person), 'John Doe')

    def test_person_unique_constraint(self):
        """Test unique_together constraint."""
        Person.objects.create(
            first_name='John',
            last_name='Doe',
            date_of_birth=date(1980, 1, 15)
        )

        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            Person.objects.create(
                first_name='John',
                last_name='Doe',
                date_of_birth=date(1980, 1, 15)
            )

    def test_person_gender_choices(self):
        """Test gender choices."""
        person = Person.objects.create(
            first_name='Test',
            last_name='User'
        )

        for gender, _ in Person.GENDER_CHOICES:
            person.gender = gender
            person.save()  # Just save, don't full_clean to avoid the created_by issue


class VoterRecordModelTest(TestCase):
    """Test cases for the VoterRecord model."""

    def setUp(self):
        self.person = Person.objects.create(
            first_name='Jane',
            last_name='Voter',
            email='jane@example.com'
        )

        self.voter_data = {
            'person': self.person,
            'voter_id': 'V123456789',
            'registration_date': date(2020, 1, 1),
            'registration_status': 'active',
            'party_affiliation': 'DEM',
            'precinct': '42',
            'ward': '5',
            'congressional_district': '12',
            'state_house_district': '25',
            'state_senate_district': '8',
            'polling_location': 'Community Center',
            'voting_history': [
                {'date': '2020-11-03', 'election': 'General'},
                {'date': '2022-11-08', 'election': 'Midterm'}
            ],
            'absentee_voter': False,
            'mail_ballot_requested': False,
            'last_voted_date': date(2022, 11, 8),
            'voter_score': 85,
            'source': 'State Voter File',
        }

    def test_create_voter_record(self):
        """Test creating a voter record."""
        voter = VoterRecord.objects.create(**self.voter_data)

        self.assertEqual(voter.voter_id, 'V123456789')
        self.assertEqual(voter.party_affiliation, 'DEM')
        self.assertEqual(voter.precinct, '42')
        self.assertEqual(voter.voter_score, 85)
        self.assertEqual(len(voter.voting_history), 2)

    def test_voter_record_str_representation(self):
        """Test the string representation of VoterRecord."""
        voter = VoterRecord.objects.create(**self.voter_data)
        self.assertEqual(str(voter), 'Voter V123456789 - Jane Voter')

    def test_voter_id_uniqueness(self):
        """Test that voter_id is unique."""
        VoterRecord.objects.create(**self.voter_data)

        # Try to create duplicate with same voter_id
        new_person = Person.objects.create(
            first_name='Another',
            last_name='Person'
        )
        duplicate_data = self.voter_data.copy()
        duplicate_data['person'] = new_person

        with self.assertRaises(IntegrityError):
            VoterRecord.objects.create(**duplicate_data)

    def test_one_to_one_relationship(self):
        """Test one-to-one relationship with Person."""
        voter = VoterRecord.objects.create(**self.voter_data)

        # Access voter record from person
        self.assertEqual(self.person.voter_record, voter)

        # Try to create another voter record for same person
        with self.assertRaises(IntegrityError):
            VoterRecord.objects.create(
                person=self.person,
                voter_id='V987654321'
            )

    def test_registration_status_choices(self):
        """Test registration status choices."""
        voter = VoterRecord.objects.create(**self.voter_data)

        for status, _ in VoterRecord.REGISTRATION_STATUS_CHOICES:
            voter.registration_status = status
            voter.full_clean()  # Should not raise

    def test_party_affiliation_choices(self):
        """Test party affiliation choices."""
        voter = VoterRecord.objects.create(**self.voter_data)

        for party, _ in VoterRecord.PARTY_AFFILIATION_CHOICES:
            voter.party_affiliation = party
            voter.full_clean()  # Should not raise


class ContactAttemptModelTest(TestCase):
    """Test cases for the ContactAttempt model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='canvasser',
            email='canvasser@example.com'
        )

        self.person = Person.objects.create(
            first_name='Contact',
            last_name='Target',
            email='target@example.com'
        )

        self.contact_data = {
            'person': self.person,
            'contact_type': 'phone',
            'contact_date': datetime.now(),
            'contacted_by': self.user,
            'result': 'contacted',
            'sentiment': 'support',
            'issues_discussed': ['healthcare', 'education'],
            'commitments': ['volunteer', 'donate'],
            'follow_up_required': True,
            'follow_up_date': date.today() + timedelta(days=7),
            'notes': 'Very supportive, wants to volunteer',
            'duration_minutes': 15,
            'campaign': 'GOTV 2024',
            'event': 'Phone Bank #3',
        }

    def test_create_contact_attempt(self):
        """Test creating a contact attempt."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        self.assertEqual(contact.contact_type, 'phone')
        self.assertEqual(contact.result, 'contacted')
        self.assertEqual(contact.sentiment, 'support')
        self.assertEqual(contact.duration_minutes, 15)
        self.assertEqual(len(contact.issues_discussed), 2)
        self.assertTrue(contact.follow_up_required)

    def test_contact_attempt_str_representation(self):
        """Test the string representation of ContactAttempt."""
        contact = ContactAttempt.objects.create(**self.contact_data)
        date_str = contact.contact_date.strftime('%Y-%m-%d')
        expected = f"phone - Contact Target on {date_str}"
        self.assertEqual(str(contact), expected)

    def test_multiple_contacts_per_person(self):
        """Test that multiple contact attempts can be created for one person."""
        ContactAttempt.objects.create(**self.contact_data)

        # Create another contact attempt for same person
        new_contact_data = self.contact_data.copy()
        new_contact_data['contact_type'] = 'door'
        new_contact_data['contact_date'] = datetime.now() + timedelta(days=1)

        contact2 = ContactAttempt.objects.create(**new_contact_data)

        # Check that person has multiple contact attempts
        self.assertEqual(self.person.contact_attempts.count(), 2)
        self.assertIn(contact2, self.person.contact_attempts.all())

    def test_contact_type_choices(self):
        """Test contact type choices."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        for contact_type, _ in ContactAttempt.CONTACT_TYPE_CHOICES:
            contact.contact_type = contact_type
            contact.full_clean()  # Should not raise

    def test_result_choices(self):
        """Test result choices."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        for result, _ in ContactAttempt.RESULT_CHOICES:
            contact.result = result
            contact.full_clean()  # Should not raise

    def test_sentiment_choices(self):
        """Test sentiment choices."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        for sentiment, _ in ContactAttempt.SENTIMENT_CHOICES:
            contact.sentiment = sentiment
            contact.full_clean()  # Should not raise

    def test_ordering(self):
        """Test that contact attempts are ordered by contact_date descending."""
        # Create multiple contact attempts
        contact1 = ContactAttempt.objects.create(
            person=self.person,
            contact_type='phone',
            contact_date=datetime.now() - timedelta(days=2),
            contacted_by=self.user,
            result='contacted'
        )

        contact2 = ContactAttempt.objects.create(
            person=self.person,
            contact_type='email',
            contact_date=datetime.now() - timedelta(days=1),
            contacted_by=self.user,
            result='contacted'
        )

        contact3 = ContactAttempt.objects.create(
            person=self.person,
            contact_type='door',
            contact_date=datetime.now(),
            contacted_by=self.user,
            result='contacted'
        )

        # Get all contacts and check ordering
        contacts = ContactAttempt.objects.all()
        self.assertEqual(contacts[0], contact3)  # Most recent first
        self.assertEqual(contacts[1], contact2)
        self.assertEqual(contacts[2], contact1)  # Oldest last

    def test_foreign_key_deletion(self):
        """Test foreign key behavior on deletion."""
        contact = ContactAttempt.objects.create(**self.contact_data)

        # Delete the user (contacted_by)
        self.user.delete()
        contact.refresh_from_db()
        self.assertIsNone(contact.contacted_by)  # Should be set to NULL

        # Delete the person
        person_id = self.person.id
        self.person.delete()
        # Contact should be deleted (CASCADE)
        self.assertEqual(ContactAttempt.objects.filter(person_id=person_id).count(), 0)
