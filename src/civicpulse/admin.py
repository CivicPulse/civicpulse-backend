from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    Address,
    Campaign,
    Candidate,
    CheckingAccount,
    ContactAttempt,
    ContactEffort,
    District,
    Donation,
    DonationSyncJob,
    EffortAssignment,
    Election,
    ElectionDate,
    ElectionVoter,
    Email,
    GeocodingError,
    GeocodingJob,
    ImportJob,
    Office,
    Organization,
    Person,
    PhoneNumber,
    StripeConnection,
    Transaction,
    VoterAddress,
    VoterEmail,
    VoterPhoneNumber,
    VoterRecord,
)


class PhoneNumberInline(admin.TabularInline):
    model = PhoneNumber
    extra = 1


class EmailInline(admin.TabularInline):
    model = Email
    extra = 1


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


class VoterRecordInline(admin.StackedInline):
    model = VoterRecord
    extra = 0
    max_num = 1
    fieldsets = [
        (
            "Demographics",
            {
                "fields": [
                    "registered_party",
                    "gender",
                    "age",
                    "ethnicity",
                    "marital_status",
                    "spoken_language",
                    "military_status",
                    "changed_party",
                ]
            },
        ),
        (
            "Location",
            {
                "fields": [
                    "latitude",
                    "longitude",
                    "apartment_type",
                    "street_number_parity",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Voting Scores",
            {
                "fields": [
                    "likelihood_general",
                    "likelihood_primary",
                    "likelihood_combined",
                ]
            },
        ),
        (
            "Voting History",
            {
                "fields": [
                    ("voted_general_2024", "voted_primary_2024"),
                    ("voted_general_2022", "voted_primary_2022"),
                    ("voted_general_2020", "voted_primary_2020"),
                    ("voted_general_2018", "voted_primary_2018"),
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Household",
            {
                "fields": [
                    "household_party",
                    "mailing_household_size",
                    "mailing_family_id",
                    "mailing_household_count",
                    "mailing_household_party",
                    "cell_phone_confidence",
                ],
                "classes": ["collapse"],
            },
        ),
    ]


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "voter_id",
        "organization",
        "job_title",
        "user",
        "created_at",
    ]
    list_filter = ["organization", "created_at"]
    search_fields = ["first_name", "last_name", "nickname", "organization", "voter_id"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [PhoneNumberInline, EmailInline, AddressInline, VoterRecordInline]
    fieldsets = [
        (None, {"fields": ["first_name", "middle_name", "last_name", "nickname"]}),
        ("Voter Info", {"fields": ["voter_id"]}),
        ("Work", {"fields": ["organization", "job_title"]}),
        ("User Account", {"fields": ["user"], "classes": ["collapse"]}),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]


# Organization admin (governing bodies that contain offices)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "organization_type",
        "city",
        "county",
        "state",
        "office_count",
    ]
    list_filter = ["organization_type", "state"]
    search_fields = ["name", "city", "county"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "organization_type", "description"]}),
        ("Jurisdiction", {"fields": ["city", "county", "state"]}),
        ("Links", {"fields": ["website"], "classes": ["collapse"]}),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    @admin.display(description="Offices")
    def office_count(self, obj):
        return obj.offices.count()


# Election-related admin classes


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "organization",
        "level",
        "city",
        "county",
        "state",
        "term_length_years",
        "election_count",
    ]
    list_filter = ["organization", "level", "state"]
    search_fields = ["name", "city", "county", "organization__name"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "level", "description"]}),
        ("Organization", {"fields": ["organization"]}),
        ("Jurisdiction", {"fields": ["city", "county", "state"]}),
        ("Term", {"fields": ["term_length_years"]}),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    @admin.display(description="Elections")
    def election_count(self, obj):
        return obj.elections.count()


class ElectionDateInline(admin.TabularInline):
    model = ElectionDate
    extra = 1


class CandidateInline(admin.TabularInline):
    model = Candidate
    extra = 0
    raw_id_fields = ["person"]
    readonly_fields = ["created_at"]
    fields = ["person", "party_affiliation", "is_incumbent", "status", "created_at"]


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = [
        "__str__",
        "election_type",
        "year",
        "status",
        "election_day",
        "candidate_count",
        "geocoding_status",
    ]
    list_filter = ["election_type", "status", "year", "office__level", "office__state"]
    search_fields = ["office__name", "office__city", "description"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["office", "parent_election"]
    inlines = [CandidateInline, ElectionDateInline]
    actions = ["trigger_geocoding"]
    filter_horizontal = ["districts"]
    fieldsets = [
        (
            None,
            {"fields": ["office", "election_type", "year", "status", "description"]},
        ),
        ("Parent Election", {"fields": ["parent_election"], "classes": ["collapse"]}),
        (
            "Key Dates",
            {
                "fields": [
                    ("qualifying_start", "qualifying_end"),
                    "registration_deadline",
                    "absentee_request_deadline",
                    ("early_voting_start", "early_voting_end"),
                    "election_day",
                    "certification_date",
                ]
            },
        ),
        (
            "Geographic Coverage",
            {
                "fields": ["districts"],
                "description": "Geographic districts this election covers (counties, precincts, etc.)",
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    @admin.display(description="Candidates")
    def candidate_count(self, obj):
        return obj.candidates.count()

    @admin.display(description="Geocoding")
    def geocoding_status(self, obj):
        """Show geocoding job status for this election."""
        voters_total = obj.election_voters.count()
        voters_geocoded = obj.election_voters.filter(location__isnull=False).count()

        if voters_total == 0:
            return format_html('<span style="color: gray;">No voters</span>')

        percentage = round((voters_geocoded / voters_total) * 100)

        if percentage == 100:
            color = "green"
        elif percentage >= 50:
            color = "orange"
        else:
            color = "red"

        return format_html(
            '<span style="color: {};">{}/{} ({}%)</span>',
            color,
            voters_geocoded,
            voters_total,
            percentage,
        )

    @admin.action(description="Trigger geocoding for selected elections")
    def trigger_geocoding(self, request, queryset):
        """Queue geocoding tasks for voters in selected elections."""
        from .tasks import geocode_election_voters

        count = 0
        for election in queryset:
            # Check if there are voters needing geocoding
            needs_geocoding = election.election_voters.filter(
                location__isnull=True
            ).count()

            if needs_geocoding > 0:
                geocode_election_voters.delay(str(election.pk))
                count += 1

        if count > 0:
            self.message_user(
                request,
                f"Geocoding queued for {count} election(s). Check Geocoding Jobs for progress.",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "No elections with voters needing geocoding.",
                messages.WARNING,
            )


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ["person", "election", "party_affiliation", "is_incumbent", "status"]
    list_filter = ["status", "party_affiliation", "is_incumbent", "election__year"]
    search_fields = [
        "person__first_name",
        "person__last_name",
        "election__office__name",
    ]
    raw_id_fields = ["person", "election"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["person", "election", "party_affiliation"]}),
        ("Status", {"fields": ["status", "is_incumbent"]}),
        (
            "Campaign Info",
            {
                "fields": ["campaign_website", "campaign_slogan"],
                "classes": ["collapse"],
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]


# Campaign admin (organization working to elect a candidate)


class ContactEffortInline(admin.TabularInline):
    """Inline for drives within a campaign."""

    model = ContactEffort
    extra = 0
    fields = ["name", "is_active", "uses_election_voters", "created_at"]
    readonly_fields = ["created_at"]
    show_change_link = True


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "is_active",
        "candidate",
        "election",
        "drive_count",
        "created_by",
        "created_at",
    ]
    list_filter = ["is_active", "election__year", "created_at"]
    search_fields = [
        "name",
        "description",
        "candidate__person__first_name",
        "candidate__person__last_name",
        "election__office__name",
    ]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["candidate", "election", "created_by"]
    inlines = [ContactEffortInline]
    fieldsets = [
        (None, {"fields": ["name", "description", "is_active"]}),
        (
            "Associations",
            {
                "fields": ["candidate", "election"],
                "description": "Link to a candidate and/or election (both optional)",
            },
        ),
        (
            "Metadata",
            {
                "fields": ["created_by", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Drives")
    def drive_count(self, obj):
        return obj.drives.count()


class EffortAssignmentInline(admin.TabularInline):
    model = EffortAssignment
    extra = 0
    raw_id_fields = ["person"]
    readonly_fields = ["status", "assigned_at", "locked_by", "locked_at"]


@admin.register(ContactEffort)
class ContactEffortAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "is_active",
        "campaign",
        "election",
        "candidate",
        "assignment_count",
        "created_by",
        "created_at",
    ]
    list_filter = ["is_active", "campaign", "election__year", "created_at"]
    search_fields = ["name", "description", "campaign__name", "election__office__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["campaign", "election", "candidate"]
    inlines = [EffortAssignmentInline]
    fieldsets = [
        (None, {"fields": ["name", "description", "is_active"]}),
        ("Script", {"fields": ["script"]}),
        (
            "Campaign & Election",
            {
                "fields": ["campaign", "election", "candidate"],
                "description": "Link to a parent campaign and/or election",
            },
        ),
        (
            "Metadata",
            {
                "fields": ["created_by", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Assignments")
    def assignment_count(self, obj):
        return obj.assignments.count()


@admin.register(ContactAttempt)
class ContactAttemptAdmin(admin.ModelAdmin):
    list_display = [
        "person",
        "effort",
        "contact_type",
        "outcome",
        "contacted_by",
        "created_at",
    ]
    list_filter = ["effort", "outcome", "contact_type", "created_at"]
    search_fields = ["person__first_name", "person__last_name", "notes"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["person"]
    fieldsets = [
        (None, {"fields": ["effort", "person", "contacted_by"]}),
        ("Contact Details", {"fields": ["contact_type", "phone_number_used"]}),
        ("Outcome", {"fields": ["outcome", "notes", "callback_time"]}),
        ("Metadata", {"fields": ["created_at"], "classes": ["collapse"]}),
    ]


# Election Voter admin classes


class VoterPhoneNumberInline(admin.TabularInline):
    model = VoterPhoneNumber
    extra = 0


class VoterEmailInline(admin.TabularInline):
    model = VoterEmail
    extra = 0


class VoterAddressInline(admin.TabularInline):
    model = VoterAddress
    extra = 0


@admin.register(ElectionVoter)
class ElectionVoterAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "voter_id",
        "election",
        "registered_party",
        "likelihood_combined",
        "created_at",
    ]
    list_filter = ["election", "registered_party", "created_at"]
    search_fields = ["first_name", "last_name", "voter_id", "election__office__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["election"]
    inlines = [VoterPhoneNumberInline, VoterEmailInline, VoterAddressInline]
    fieldsets = [
        (
            None,
            {"fields": ["election", "voter_id", "first_name", "middle_name", "last_name", "nickname"]},
        ),
        (
            "Demographics",
            {
                "fields": [
                    "registered_party",
                    "gender",
                    "age",
                    "ethnicity",
                    "marital_status",
                    "spoken_language",
                    "military_status",
                    "changed_party",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Location",
            {
                "fields": ["latitude", "longitude", "apartment_type", "street_number_parity"],
                "classes": ["collapse"],
            },
        ),
        (
            "Voting Scores",
            {
                "fields": [
                    "likelihood_general",
                    "likelihood_primary",
                    "likelihood_combined",
                ]
            },
        ),
        (
            "Voting History",
            {
                "fields": ["voting_history"],
                "classes": ["collapse"],
            },
        ),
        (
            "Household",
            {
                "fields": [
                    "household_party",
                    "mailing_household_size",
                    "mailing_family_id",
                    "mailing_household_count",
                    "mailing_household_party",
                    "cell_phone_confidence",
                ],
                "classes": ["collapse"],
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]


# Jobs admin


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "import_type", "created_at"]
    list_filter = ["status", "import_type", "created_at"]
    readonly_fields = ["created_at", "updated_at", "result"]
    fieldsets = [
        (
            None,
            {
                "fields": ["import_type", "status"],
            },
        ),
        (
            "File",
            {
                "fields": ["import_file"],
            },
        ),
        (
            "Result",
            {
                "fields": ["result"],
                "classes": ["collapse"],
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]


@admin.register(GeocodingJob)
class GeocodingJobAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "created_at", "attempts"]
    list_filter = ["status", "created_at"]
    readonly_fields = ["created_at", "updated_at", "result"]
    fieldsets = [
        (None, {"fields": ["status", "attempts"]}),
        (
            "Result",
            {
                "fields": ["result"],
                "classes": ["collapse"],
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]


@admin.register(GeocodingError)
class GeocodingErrorAdmin(admin.ModelAdmin):
    list_display = ["id", "election_voter", "error_type", "created_at"]
    list_filter = ["error_type", "created_at"]
    raw_id_fields = ["election_voter"]
    readonly_fields = ["created_at"]
    fieldsets = [
        (None, {"fields": ["election_voter", "error_type", "error_message"]}),
        ("Metadata", {"fields": ["created_at"], "classes": ["collapse"]}),
    ]


# Financial admin


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    raw_id_fields = ["donation"]
    readonly_fields = ["created_at"]
    fields = ["donation", "amount", "transaction_type", "status", "created_at"]


@admin.register(CheckingAccount)
class CheckingAccountAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "organization", "status", "balance", "created_at"]
    list_filter = ["status", "created_at"]
    raw_id_fields = ["organization"]
    readonly_fields = ["created_at", "updated_at", "balance"]
    inlines = [TransactionInline]
    fieldsets = [
        (
            None,
            {
                "fields": ["organization", "name", "status"],
            },
        ),
        (
            "Account Details",
            {
                "fields": ["account_number", "routing_number", "balance"],
                "classes": ["collapse"],
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "donation",
        "amount",
        "transaction_type",
        "status",
        "created_at",
    ]
    list_filter = ["transaction_type", "status", "created_at"]
    raw_id_fields = ["donation"]
    readonly_fields = ["created_at"]
    fieldsets = [
        (
            None,
            {
                "fields": ["donation", "amount", "transaction_type", "status"],
            },
        ),
        ("Metadata", {"fields": ["created_at"], "classes": ["collapse"]}),
    ]


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "donor_name",
        "amount",
        "donation_type",
        "candidate",
        "created_at",
    ]
    list_filter = ["donation_type", "candidate__election__year", "created_at"]
    search_fields = ["first_name", "last_name", "email"]
    raw_id_fields = ["candidate"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (
            None,
            {
                "fields": ["first_name", "last_name", "email", "phone_number"],
            },
        ),
        (
            "Donation",
            {
                "fields": ["amount", "donation_type", "candidate"],
            },
        ),
        (
            "Metadata",
            {
                "fields": ["created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Donor Name")
    def donor_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


@admin.register(DonationSyncJob)
class DonationSyncJobAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "created_at"]
    list_filter = ["status", "created_at"]
    readonly_fields = ["created_at", "updated_at", "result"]
    fieldsets = [
        (None, {"fields": ["status"]}),
        (
            "Result",
            {
                "fields": ["result"],
                "classes": ["collapse"],
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "district_type", "state", "created_at"]
    list_filter = ["district_type", "state", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (
            None,
            {
                "fields": ["name", "district_type", "state", "description"],
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]


@admin.register(StripeConnection)
class StripeConnectionAdmin(admin.ModelAdmin):
    list_display = ["id", "organization", "stripe_account_id", "created_at"]
    list_filter = ["created_at"]
    raw_id_fields = ["organization"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (
            None,
            {
                "fields": ["organization", "stripe_account_id"],
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]