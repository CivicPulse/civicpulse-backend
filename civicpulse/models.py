import uuid

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class User(AbstractUser):
    """Extended User model with additional fields for roles and permissions."""

    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('organizer', 'Organizer'),
        ('volunteer', 'Volunteer'),
        ('viewer', 'Viewer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    organization = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')]
    )
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['organization']),
        ]

    def __str__(self):
        return f"{self.username} ({self.role})"


class Person(models.Model):
    """Model representing a person/voter with all their information."""

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('U', 'Unknown'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Basic Information
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    suffix = models.CharField(max_length=10, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='U')

    # Contact Information
    email = models.EmailField(blank=True, db_index=True)
    phone_primary = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')]
    )
    phone_secondary = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number.')]
    )

    # Address Information
    street_address = models.CharField(max_length=255, blank=True)
    apartment_number = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    county = models.CharField(max_length=100, blank=True)

    # Additional Information
    occupation = models.CharField(max_length=100, blank=True)
    employer = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)

    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='persons_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'persons'
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['email']),
            models.Index(fields=['phone_primary']),
            models.Index(fields=['zip_code']),
            models.Index(fields=['created_at']),
        ]
        unique_together = [['first_name', 'last_name', 'date_of_birth']]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        if self.suffix:
            parts.append(self.suffix)
        return ' '.join(parts)


class VoterRecord(models.Model):
    """Model for voter registration and voting history information."""

    REGISTRATION_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
    ]

    PARTY_AFFILIATION_CHOICES = [
        ('DEM', 'Democratic'),
        ('REP', 'Republican'),
        ('IND', 'Independent'),
        ('GRN', 'Green'),
        ('LIB', 'Libertarian'),
        ('OTH', 'Other'),
        ('NON', 'No Party Affiliation'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        related_name='voter_record'
    )

    # Registration Information
    voter_id = models.CharField(max_length=50, unique=True, db_index=True)
    registration_date = models.DateField(null=True, blank=True)
    registration_status = models.CharField(
        max_length=20,
        choices=REGISTRATION_STATUS_CHOICES,
        default='active'
    )
    party_affiliation = models.CharField(
        max_length=3,
        choices=PARTY_AFFILIATION_CHOICES,
        default='NON'
    )

    # Voting Location
    precinct = models.CharField(max_length=50, blank=True)
    ward = models.CharField(max_length=50, blank=True)
    congressional_district = models.CharField(max_length=10, blank=True)
    state_house_district = models.CharField(max_length=10, blank=True)
    state_senate_district = models.CharField(max_length=10, blank=True)
    polling_location = models.CharField(max_length=255, blank=True)

    # Voting History (stored as JSON for flexibility)
    voting_history = models.JSONField(default=list, blank=True)

    # Absentee/Mail Voting
    absentee_voter = models.BooleanField(default=False)
    mail_ballot_requested = models.BooleanField(default=False)
    mail_ballot_sent_date = models.DateField(null=True, blank=True)
    mail_ballot_returned_date = models.DateField(null=True, blank=True)

    # Metadata
    last_voted_date = models.DateField(null=True, blank=True)
    voter_score = models.IntegerField(default=0)  # Frequency of voting (0-100)
    source = models.CharField(max_length=100, blank=True)  # Data source
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voter_records'
        indexes = [
            models.Index(fields=['voter_id']),
            models.Index(fields=['registration_status']),
            models.Index(fields=['party_affiliation']),
            models.Index(fields=['precinct']),
            models.Index(fields=['ward']),
            models.Index(fields=['last_voted_date']),
        ]

    def __str__(self):
        return f"Voter {self.voter_id} - {self.person.full_name}"


class ContactAttempt(models.Model):
    """Model for tracking outreach and contact attempts."""

    CONTACT_TYPE_CHOICES = [
        ('phone', 'Phone Call'),
        ('text', 'Text Message'),
        ('email', 'Email'),
        ('door', 'Door Knock'),
        ('mail', 'Postal Mail'),
        ('social', 'Social Media'),
        ('event', 'Event'),
        ('other', 'Other'),
    ]

    RESULT_CHOICES = [
        ('contacted', 'Successfully Contacted'),
        ('no_answer', 'No Answer'),
        ('left_message', 'Left Message'),
        ('wrong_number', 'Wrong Number'),
        ('refused', 'Refused'),
        ('callback', 'Callback Requested'),
        ('not_home', 'Not Home'),
        ('moved', 'Moved'),
        ('deceased', 'Deceased'),
        ('other', 'Other'),
    ]

    SENTIMENT_CHOICES = [
        ('strong_support', 'Strong Support'),
        ('support', 'Support'),
        ('neutral', 'Neutral'),
        ('oppose', 'Oppose'),
        ('strong_oppose', 'Strong Oppose'),
        ('undecided', 'Undecided'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='contact_attempts'
    )

    # Contact Information
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPE_CHOICES)
    contact_date = models.DateTimeField()
    contacted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='contacts_made'
    )

    # Result Information
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    sentiment = models.CharField(
        max_length=20,
        choices=SENTIMENT_CHOICES,
        blank=True
    )

    # Conversation Details
    issues_discussed = models.JSONField(default=list, blank=True)
    commitments = models.JSONField(default=list, blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)

    # Notes and Details
    notes = models.TextField(blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)

    # Campaign/Event Association
    campaign = models.CharField(max_length=100, blank=True)
    event = models.CharField(max_length=100, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contact_attempts'
        indexes = [
            models.Index(fields=['contact_date']),
            models.Index(fields=['contact_type']),
            models.Index(fields=['result']),
            models.Index(fields=['sentiment']),
            models.Index(fields=['follow_up_required', 'follow_up_date']),
            models.Index(fields=['campaign']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-contact_date']

    def __str__(self):
        date_str = self.contact_date.strftime('%Y-%m-%d')
        return f"{self.contact_type} - {self.person.full_name} on {date_str}"
