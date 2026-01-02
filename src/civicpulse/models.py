import uuid

from django.contrib.auth.models import User
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
from django.db import models


class Person(models.Model):
    """A person record for storing contact and metadata."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    nickname = models.CharField(max_length=100, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    job_title = models.CharField(max_length=200, blank=True)
    voter_id = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text="External voter file ID",
    )
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="person",
        help_text="Optional link to a Django user account",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "people"
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
        ]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        """Return the person's full name."""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(parts)


class PhoneNumber(models.Model):
    """Phone number associated with a person."""

    class PhoneType(models.TextChoices):
        MOBILE = "mobile", "Mobile"
        HOME = "home", "Home"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="phone_numbers"
    )
    number = models.CharField(max_length=20)
    type = models.CharField(
        max_length=10, choices=PhoneType.choices, default=PhoneType.MOBILE
    )
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_primary", "type"]

    def __str__(self):
        return f"{self.number} ({self.get_type_display()})"


class Email(models.Model):
    """Email address associated with a person."""

    class EmailType(models.TextChoices):
        PERSONAL = "personal", "Personal"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="emails")
    email = models.EmailField()
    type = models.CharField(
        max_length=10, choices=EmailType.choices, default=EmailType.PERSONAL
    )
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_primary", "type"]

    def __str__(self):
        return f"{self.email} ({self.get_type_display()})"


class Address(models.Model):
    """Physical address associated with a person."""

    class AddressType(models.TextChoices):
        HOME = "home", "Home"
        WORK = "work", "Work"
        MAILING = "mailing", "Mailing"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="addresses"
    )
    type = models.CharField(
        max_length=10, choices=AddressType.choices, default=AddressType.HOME
    )
    street_address = models.CharField(max_length=255)
    street_address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, help_text="US state abbreviation")
    zip_code = models.CharField(max_length=10)
    is_primary = models.BooleanField(default=False)

    # Geocoded location (optional - populated by geocoding service)
    location = gis_models.PointField(
        srid=4326,
        geography=True,
        null=True,
        blank=True,
        help_text="Geocoded location of this address",
    )

    class Meta:
        verbose_name_plural = "addresses"
        ordering = ["-is_primary", "type"]

    def __str__(self):
        return f"{self.street_address}, {self.city}, {self.state} {self.zip_code}"


class VoterRecord(models.Model):
    """Voter-specific data linked to a Person."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.OneToOneField(
        Person, on_delete=models.CASCADE, related_name="voter_record"
    )

    # Demographics
    registered_party = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=1, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    ethnicity = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(max_length=20, blank=True)
    spoken_language = models.CharField(max_length=50, blank=True)
    military_status = models.CharField(max_length=50, blank=True)
    changed_party = models.BooleanField(null=True, blank=True)

    # Location (legacy lat/lon kept for backwards compatibility)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    # GeoDjango spatial point (auto-populated from lat/lon on save)
    location = gis_models.PointField(
        srid=4326,
        geography=True,
        null=True,
        blank=True,
        help_text="GPS location (longitude, latitude)",
    )
    apartment_type = models.CharField(max_length=50, blank=True)
    street_number_parity = models.CharField(max_length=10, blank=True)

    # Contact metadata
    cell_phone_confidence = models.CharField(max_length=10, blank=True)

    # Voting scores
    likelihood_general = models.CharField(max_length=20, blank=True)
    likelihood_primary = models.CharField(max_length=20, blank=True)
    likelihood_combined = models.CharField(max_length=20, blank=True)

    # Voting history - General elections
    voted_general_2024 = models.BooleanField(null=True, blank=True)
    voted_general_2022 = models.BooleanField(null=True, blank=True)
    voted_general_2020 = models.BooleanField(null=True, blank=True)
    voted_general_2018 = models.BooleanField(null=True, blank=True)

    # Voting history - Primary elections
    voted_primary_2024 = models.BooleanField(null=True, blank=True)
    voted_primary_2022 = models.BooleanField(null=True, blank=True)
    voted_primary_2020 = models.BooleanField(null=True, blank=True)
    voted_primary_2018 = models.BooleanField(null=True, blank=True)

    # Household
    household_party = models.CharField(max_length=100, blank=True)
    mailing_household_size = models.PositiveIntegerField(null=True, blank=True)
    mailing_family_id = models.CharField(max_length=50, blank=True)
    mailing_household_count = models.PositiveIntegerField(null=True, blank=True)
    mailing_household_party = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "voter record"
        verbose_name_plural = "voter records"

    def __str__(self):
        return f"Voter record for {self.person}"

    def save(self, *args, **kwargs):
        """Auto-populate location PointField from lat/lon if not set."""
        if self.latitude and self.longitude and not self.location:
            self.location = Point(
                float(self.longitude), float(self.latitude), srid=4326
            )
        super().save(*args, **kwargs)


class Office(models.Model):
    """Represents an elected office position."""

    class Level(models.TextChoices):
        FEDERAL = "federal", "Federal"
        STATE = "state", "State"
        COUNTY = "county", "County"
        CITY = "city", "City"
        SCHOOL_DISTRICT = "school_district", "School District"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=200, help_text="e.g., 'Mayor', 'City Council Seat 3'"
    )
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.CITY)

    # Jurisdiction fields
    city = models.CharField(max_length=100, blank=True)
    county = models.CharField(max_length=100, blank=True)
    state = models.CharField(
        max_length=2, blank=True, help_text="US state abbreviation"
    )

    term_length_years = models.PositiveIntegerField(
        null=True, blank=True, help_text="Term length in years"
    )
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["level", "state", "city", "name"]
        indexes = [
            models.Index(fields=["level"]),
            models.Index(fields=["state", "city"]),
        ]

    def __str__(self):
        parts = [self.name]
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        return " - ".join(parts)


class Election(models.Model):
    """A specific election race for an office."""

    class ElectionType(models.TextChoices):
        GENERAL = "general", "General Election"
        PRIMARY = "primary", "Primary Election"
        SPECIAL = "special", "Special Election"
        RUNOFF = "runoff", "Runoff Election"

    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CERTIFIED = "certified", "Certified"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    office = models.ForeignKey(
        Office, on_delete=models.CASCADE, related_name="elections"
    )
    election_type = models.CharField(
        max_length=20, choices=ElectionType.choices, default=ElectionType.GENERAL
    )
    year = models.PositiveIntegerField(help_text="Election year (e.g., 2024)")

    # Parent election relationship (e.g., Primary -> General)
    parent_election = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_elections",
        help_text="Parent election (e.g., the General election this Primary feeds into)",
    )

    # Key dates
    qualifying_start = models.DateField(null=True, blank=True)
    qualifying_end = models.DateField(null=True, blank=True)
    registration_deadline = models.DateField(null=True, blank=True)
    absentee_request_deadline = models.DateField(null=True, blank=True)
    early_voting_start = models.DateField(null=True, blank=True)
    early_voting_end = models.DateField(null=True, blank=True)
    election_day = models.DateField(null=True, blank=True)
    certification_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.UPCOMING
    )
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-election_day"]
        indexes = [
            models.Index(fields=["year"]),
            models.Index(fields=["status"]),
            models.Index(fields=["election_day"]),
            models.Index(fields=["office", "year"]),
        ]

    def __str__(self):
        return f"{self.office.name} - {self.get_election_type_display()} {self.year}"


class ElectionDate(models.Model):
    """Flexible additional dates for an election."""

    class DateType(models.TextChoices):
        CANDIDATE_FORUM = "candidate_forum", "Candidate Forum"
        DEBATE = "debate", "Debate"
        FILING_DEADLINE = "filing_deadline", "Filing Deadline"
        CAMPAIGN_EVENT = "campaign_event", "Campaign Event"
        FUNDRAISING_DEADLINE = "fundraising_deadline", "Fundraising Deadline"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(
        Election, on_delete=models.CASCADE, related_name="additional_dates"
    )
    date_type = models.CharField(
        max_length=30, choices=DateType.choices, default=DateType.OTHER
    )
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.election} - {self.get_date_type_display()} ({self.date})"


class Candidate(models.Model):
    """Represents a candidate in an election, optionally linked to a Person."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        WITHDRAWN = "withdrawn", "Withdrawn"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Candidate name (used if not linked to a Person record)",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidacies",
        help_text="Optional link to an existing Person record",
    )
    election = models.ForeignKey(
        Election, on_delete=models.CASCADE, related_name="candidates"
    )
    party_affiliation = models.CharField(max_length=50, blank=True)
    is_incumbent = models.BooleanField(default=False)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.ACTIVE
    )

    # Optional campaign info
    campaign_website = models.URLField(blank=True)
    campaign_slogan = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-election__year", "name"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["party_affiliation"]),
        ]

    @property
    def display_name(self):
        """Return the candidate's display name."""
        if self.person:
            return self.person.full_name
        return self.name or "Unknown Candidate"

    def __str__(self):
        return f"{self.display_name} - {self.election}"


class Campaign(models.Model):
    """
    Represents the organization/effort to elect a candidate or advance an issue.
    Groups multiple Drives (ContactEfforts) under one umbrella.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=200, help_text="e.g., 'Smith for Mayor 2024'"
    )
    description = models.TextField(blank=True)

    # Links (both optional - allows candidate campaigns AND issue-based campaigns)
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="campaigns",
        help_text="The candidate this campaign supports (optional for issue-based campaigns)",
    )
    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="campaigns",
        help_text="The election this campaign is associated with (optional)",
    )

    # Status
    is_active = models.BooleanField(default=True)

    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="campaigns",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ContactEffort(models.Model):
    """
    A voter contact drive (outreach effort).

    In the UI, this is called a "Drive" to distinguish it from the parent
    Campaign (the organization working to elect a candidate).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    script = models.TextField(
        blank=True, help_text="Script or talking points for callers/texters"
    )
    is_active = models.BooleanField(default=True)

    # Optional election association
    election = models.ForeignKey(
        Election,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_efforts",
        help_text="Election this effort is associated with",
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_efforts",
        help_text="Candidate this effort supports",
    )

    # Parent campaign (optional for backward compatibility)
    campaign = models.ForeignKey(
        "Campaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drives",
        help_text="Parent campaign this drive belongs to",
    )

    # Flag to indicate this effort uses ElectionVoter records
    uses_election_voters = models.BooleanField(
        default=False,
        help_text="If True, uses ElectionVoter records instead of Person records",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="contact_efforts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ContactAttempt(models.Model):
    """A single contact attempt within an effort."""

    class ContactType(models.TextChoices):
        CALL = "call", "Phone Call"
        TEXT = "text", "Text Message"
        DOOR_KNOCK = "door_knock", "Door Knock"

    class Outcome(models.TextChoices):
        # Phone/text outcomes
        NO_ANSWER = "no_answer", "No Answer"
        BUSY = "busy", "Busy Signal"
        LEFT_VOICEMAIL = "left_voicemail", "Left Voicemail"
        WRONG_NUMBER = "wrong_number", "Wrong Number"
        SPOKE_WITH = "spoke_with", "Spoke With Person"
        WILL_VOTE = "will_vote", "Will Vote for Candidate"
        REFUSED = "refused", "Refused/Do Not Contact"
        CALLBACK_REQUESTED = "callback_requested", "Callback Requested"
        # Door knock outcomes
        NOT_HOME = "not_home", "Not Home"
        LEFT_DOOR_HANGER = "left_door_hanger", "Left Door Hanger"
        SPOKE_AT_DOOR = "spoke_at_door", "Spoke at Door"
        REFUSED_DOOR = "refused_door", "Refused to Answer Door"
        NO_ACCESS = "no_access", "No Access (Gated/Locked)"

    # Terminal outcomes - person should not be contacted again in this effort
    TERMINAL_OUTCOMES = [
        Outcome.SPOKE_WITH,
        Outcome.WILL_VOTE,
        Outcome.REFUSED,
        Outcome.WRONG_NUMBER,
        Outcome.SPOKE_AT_DOOR,
        Outcome.REFUSED_DOOR,
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    effort = models.ForeignKey(
        ContactEffort, on_delete=models.CASCADE, related_name="attempts"
    )
    # Legacy: for Person-based campaigns
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="contact_attempts",
    )
    # For election-specific campaigns using ElectionVoter
    election_voter = models.ForeignKey(
        "ElectionVoter",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="contact_attempts",
    )
    contacted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="contact_attempts",
    )
    contact_type = models.CharField(
        max_length=10, choices=ContactType.choices, default=ContactType.CALL
    )
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    notes = models.TextField(blank=True, help_text="Conversation details or notes")
    phone_number_used = models.CharField(
        max_length=20, blank=True, help_text="The phone number that was called/texted"
    )
    callback_time = models.DateTimeField(
        null=True, blank=True, help_text="Requested callback time"
    )
    address_visited = models.ForeignKey(
        "Address",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_attempts",
        help_text="The address visited for door knock attempts (Person)",
    )
    voter_address_visited = models.ForeignKey(
        "VoterAddress",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_attempts",
        help_text="The address visited for door knock attempts (ElectionVoter)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["effort", "person"]),
            models.Index(fields=["effort", "election_voter"]),
            models.Index(fields=["effort", "outcome"]),
        ]

    @property
    def target(self):
        """Return the contact target (either Person or ElectionVoter)."""
        return self.election_voter or self.person

    @property
    def target_name(self):
        """Return the display name of the contact target."""
        target = self.target
        return target.full_name if target else "Unknown"

    def __str__(self):
        return f"{self.target_name} - {self.get_outcome_display()} ({self.effort.name})"


class EffortAssignment(models.Model):
    """Assigns a person or election voter to a contact effort with status tracking and locking."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    effort = models.ForeignKey(
        ContactEffort, on_delete=models.CASCADE, related_name="assignments"
    )
    # Legacy: for Person-based campaigns
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="effort_assignments",
    )
    # For election-specific campaigns using ElectionVoter
    election_voter = models.ForeignKey(
        "ElectionVoter",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="effort_assignments",
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PENDING
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    locked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locked_assignments",
        help_text="Caller currently working on this assignment",
    )
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["assigned_at"]
        indexes = [
            models.Index(fields=["effort", "status"]),
            models.Index(fields=["locked_by", "locked_at"]),
        ]
        constraints = [
            # Unique per effort + person (when person is set)
            models.UniqueConstraint(
                fields=["effort", "person"],
                condition=models.Q(person__isnull=False),
                name="unique_person_assignment",
            ),
            # Unique per effort + election_voter (when election_voter is set)
            models.UniqueConstraint(
                fields=["effort", "election_voter"],
                condition=models.Q(election_voter__isnull=False),
                name="unique_election_voter_assignment",
            ),
            # Ensure at least one target is set (person OR election_voter)
            models.CheckConstraint(
                check=~models.Q(person__isnull=True, election_voter__isnull=True),
                name="assignment_must_have_target",
            ),
        ]

    @property
    def target(self):
        """Return the assignment target (either Person or ElectionVoter)."""
        return self.election_voter or self.person

    @property
    def target_name(self):
        """Return the display name of the assignment target."""
        target = self.target
        return target.full_name if target else "Unknown"

    def __str__(self):
        return f"{self.target_name} - {self.effort.name} ({self.get_status_display()})"


class ElectionVoter(models.Model):
    """
    An election-specific voter record. Each import for an election creates
    completely independent records with NO linking between elections.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core Election Association
    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name="voters",
        help_text="The election this voter record belongs to",
    )

    # External Identifier - unique PER ELECTION
    voter_id = models.CharField(
        max_length=50,
        help_text="External voter file ID (unique within this election)",
    )

    # Basic Identity Fields
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    nickname = models.CharField(max_length=100, blank=True)

    # Demographics
    registered_party = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=1, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    ethnicity = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(max_length=20, blank=True)
    spoken_language = models.CharField(max_length=50, blank=True)
    military_status = models.CharField(max_length=50, blank=True)
    changed_party = models.BooleanField(null=True, blank=True)

    # Location (legacy lat/lon kept for backwards compatibility)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    # GeoDjango spatial point (auto-populated from lat/lon on save)
    location = gis_models.PointField(
        srid=4326,
        geography=True,
        null=True,
        blank=True,
        help_text="GPS location (longitude, latitude)",
    )
    apartment_type = models.CharField(max_length=50, blank=True)
    street_number_parity = models.CharField(max_length=10, blank=True)

    # Contact metadata
    cell_phone_confidence = models.CharField(max_length=10, blank=True)

    # Voting scores
    likelihood_general = models.CharField(max_length=20, blank=True)
    likelihood_primary = models.CharField(max_length=20, blank=True)
    likelihood_combined = models.CharField(max_length=20, blank=True)

    # Voting history - stored as JSON for flexibility across election years
    voting_history = models.JSONField(
        default=dict,
        blank=True,
        help_text="Historical voting data, e.g., {'general_2024': True, 'primary_2022': False}",
    )

    # Household data
    household_party = models.CharField(max_length=100, blank=True)
    mailing_household_size = models.PositiveIntegerField(null=True, blank=True)
    mailing_family_id = models.CharField(max_length=50, blank=True)
    mailing_household_count = models.PositiveIntegerField(null=True, blank=True)
    mailing_household_party = models.CharField(max_length=100, blank=True)

    # Import tracking
    import_batch = models.CharField(
        max_length=36, blank=True, help_text="UUID of the import batch"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "election voter"
        verbose_name_plural = "election voters"
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["election", "voter_id"],
                name="unique_voter_per_election",
            ),
        ]
        indexes = [
            models.Index(fields=["election", "voter_id"]),
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["election", "registered_party"]),
            models.Index(fields=["election", "likelihood_general"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.election})"

    @property
    def full_name(self):
        """Return the voter's full name."""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(parts)

    def save(self, *args, **kwargs):
        """Auto-populate location PointField from lat/lon if not set."""
        if self.latitude and self.longitude and not self.location:
            self.location = Point(
                float(self.longitude), float(self.latitude), srid=4326
            )
        super().save(*args, **kwargs)


class VoterPhoneNumber(models.Model):
    """Phone number associated with an election voter."""

    class PhoneType(models.TextChoices):
        MOBILE = "mobile", "Mobile"
        HOME = "home", "Home"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voter = models.ForeignKey(
        ElectionVoter,
        on_delete=models.CASCADE,
        related_name="phone_numbers",
    )
    number = models.CharField(max_length=20)
    type = models.CharField(
        max_length=10, choices=PhoneType.choices, default=PhoneType.MOBILE
    )
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_primary", "type"]

    def __str__(self):
        return f"{self.number} ({self.get_type_display()})"


class VoterEmail(models.Model):
    """Email address associated with an election voter."""

    class EmailType(models.TextChoices):
        PERSONAL = "personal", "Personal"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voter = models.ForeignKey(
        ElectionVoter,
        on_delete=models.CASCADE,
        related_name="emails",
    )
    email = models.EmailField()
    type = models.CharField(
        max_length=10, choices=EmailType.choices, default=EmailType.PERSONAL
    )
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_primary", "type"]

    def __str__(self):
        return f"{self.email} ({self.get_type_display()})"


class VoterAddress(models.Model):
    """Physical address associated with an election voter."""

    class AddressType(models.TextChoices):
        HOME = "home", "Home"
        WORK = "work", "Work"
        MAILING = "mailing", "Mailing"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voter = models.ForeignKey(
        ElectionVoter,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    type = models.CharField(
        max_length=10, choices=AddressType.choices, default=AddressType.HOME
    )
    street_address = models.CharField(max_length=255)
    street_address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, help_text="US state abbreviation")
    zip_code = models.CharField(max_length=10)
    is_primary = models.BooleanField(default=False)

    # Geocoded location (optional - populated by geocoding service)
    location = gis_models.PointField(
        srid=4326,
        geography=True,
        null=True,
        blank=True,
        help_text="Geocoded location of this address",
    )

    class Meta:
        verbose_name_plural = "voter addresses"
        ordering = ["-is_primary", "type"]

    def __str__(self):
        return f"{self.street_address}, {self.city}, {self.state} {self.zip_code}"


class ImportJob(models.Model):
    """Tracks the status and progress of async voter import jobs."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(
        Election, on_delete=models.CASCADE, related_name="import_jobs"
    )
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)  # Temporary file path
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PENDING
    )

    # Progress tracking
    total_rows = models.PositiveIntegerField(default=0)
    processed_rows = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)

    # Celery task reference
    task_id = models.CharField(max_length=255, blank=True)

    # Error details
    error_messages = models.JSONField(default=list, blank=True)

    # Timestamps
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="import_jobs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Import {self.file_name} for {self.election}"

    @property
    def progress_percentage(self):
        """Return the import progress as a percentage."""
        if self.total_rows == 0:
            return 0
        return round((self.processed_rows / self.total_rows) * 100, 1)


# =============================================================================
# GIS Models
# =============================================================================


class District(models.Model):
    """
    Represents a geographic district or precinct boundary.

    Used for spatial queries like "find all voters within this district"
    and for map visualization with boundary overlays.
    """

    class DistrictType(models.TextChoices):
        PRECINCT = "precinct", "Voting Precinct"
        CONGRESSIONAL = "congressional", "Congressional District"
        STATE_HOUSE = "state_house", "State House District"
        STATE_SENATE = "state_senate", "State Senate District"
        COUNTY = "county", "County"
        CITY = "city", "City"
        SCHOOL_DISTRICT = "school_district", "School District"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    district_type = models.CharField(
        max_length=20,
        choices=DistrictType.choices,
        default=DistrictType.PRECINCT,
    )
    identifier = models.CharField(
        max_length=50,
        blank=True,
        help_text="Official district identifier/code",
    )
    state = models.CharField(max_length=2, blank=True)
    county = models.CharField(max_length=100, blank=True)

    # Spatial boundary
    boundary = gis_models.MultiPolygonField(
        srid=4326,
        help_text="Geographic boundary of this district",
    )

    # Metadata
    source = models.CharField(
        max_length=255,
        blank=True,
        help_text="Data source (e.g., Census TIGER, state GIS)",
    )
    effective_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["district_type", "state", "name"]
        indexes = [
            models.Index(fields=["district_type", "state"]),
            models.Index(fields=["identifier"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_district_type_display()})"

    def contains_point(self, point):
        """Check if a point is within this district boundary."""
        return self.boundary.contains(point)


class GeocodingJob(models.Model):
    """Tracks the status of geocoding operations."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Target - either an election or general bulk operation
    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="geocoding_jobs",
    )

    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PENDING
    )

    # Progress tracking
    total_addresses = models.PositiveIntegerField(default=0)
    processed_addresses = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)

    # Celery task reference
    task_id = models.CharField(max_length=255, blank=True)

    # Timestamps
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="geocoding_jobs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "geocoding job"
        verbose_name_plural = "geocoding jobs"

    def __str__(self):
        target = self.election or "All"
        return f"Geocoding job for {target} ({self.get_status_display()})"

    @property
    def progress_percentage(self):
        """Return the geocoding progress as a percentage."""
        if self.total_addresses == 0:
            return 0
        return round((self.processed_addresses / self.total_addresses) * 100, 1)


class GeocodingError(models.Model):
    """Logs failed geocoding attempts for review and retry."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        GeocodingJob,
        on_delete=models.CASCADE,
        related_name="errors",
    )

    # What failed
    address_text = models.CharField(max_length=500)
    model_type = models.CharField(
        max_length=50,
        help_text="Model type: address, voter_address, election_voter, voter_record",
    )
    model_id = models.UUIDField()

    # Error details
    error_message = models.TextField()
    retry_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "geocoding error"
        verbose_name_plural = "geocoding errors"

    def __str__(self):
        return f"Geocoding error: {self.address_text[:50]}..."
