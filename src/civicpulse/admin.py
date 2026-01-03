from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    Address,
    Campaign,
    Candidate,
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
    Person,
    PhoneNumber,
    StripeConnection,
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


# Election-related admin classes


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "level",
        "city",
        "county",
        "state",
        "term_length_years",
        "election_count",
    ]
    list_filter = ["level", "state"]
    search_fields = ["name", "city", "county"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "level", "description"]}),
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


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = [
        "file_name",
        "election",
        "status",
        "progress_display",
        "created_by",
        "created_at",
    ]
    list_filter = ["status", "election", "created_at"]
    search_fields = ["file_name", "election__office__name"]
    readonly_fields = [
        "task_id",
        "total_rows",
        "processed_rows",
        "created_count",
        "updated_count",
        "error_count",
        "error_messages",
        "created_at",
        "started_at",
        "completed_at",
    ]
    raw_id_fields = ["election", "created_by"]
    fieldsets = [
        (None, {"fields": ["election", "file_name", "file_path", "status"]}),
        (
            "Progress",
            {
                "fields": [
                    "total_rows",
                    "processed_rows",
                    "created_count",
                    "updated_count",
                    "error_count",
                ]
            },
        ),
        (
            "Errors",
            {
                "fields": ["error_messages"],
                "classes": ["collapse"],
            },
        ),
        (
            "Task Info",
            {
                "fields": ["task_id"],
                "classes": ["collapse"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_by", "created_at", "started_at", "completed_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Progress")
    def progress_display(self, obj):
        return f"{obj.processed_rows}/{obj.total_rows} ({obj.progress_percentage}%)"


# =============================================================================
# Geocoding Admin
# =============================================================================


class GeocodingErrorInline(admin.TabularInline):
    model = GeocodingError
    extra = 0
    readonly_fields = ["address_text", "model_type", "model_id", "error_message", "retry_count", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(GeocodingJob)
class GeocodingJobAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "election",
        "status",
        "progress_display",
        "success_rate",
        "created_by",
        "created_at",
    ]
    list_filter = ["status", "election", "created_at"]
    search_fields = ["election__office__name", "task_id"]
    readonly_fields = [
        "task_id",
        "total_addresses",
        "processed_addresses",
        "success_count",
        "failure_count",
        "created_at",
        "started_at",
        "completed_at",
    ]
    raw_id_fields = ["election", "created_by"]
    inlines = [GeocodingErrorInline]
    actions = ["retry_failed_addresses"]
    fieldsets = [
        (None, {"fields": ["election", "status"]}),
        (
            "Progress",
            {
                "fields": [
                    "total_addresses",
                    "processed_addresses",
                    "success_count",
                    "failure_count",
                ]
            },
        ),
        (
            "Task Info",
            {
                "fields": ["task_id"],
                "classes": ["collapse"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_by", "created_at", "started_at", "completed_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Progress")
    def progress_display(self, obj):
        if obj.total_addresses == 0:
            return "0/0 (0%)"
        percentage = round((obj.processed_addresses / obj.total_addresses) * 100)
        return f"{obj.processed_addresses}/{obj.total_addresses} ({percentage}%)"

    @admin.display(description="Success Rate")
    def success_rate(self, obj):
        if obj.processed_addresses == 0:
            return "-"
        rate = round((obj.success_count / obj.processed_addresses) * 100)

        if rate >= 90:
            color = "green"
        elif rate >= 70:
            color = "orange"
        else:
            color = "red"

        return format_html(
            '<span style="color: {};">{}%</span>',
            color,
            rate,
        )

    @admin.action(description="Retry failed addresses")
    def retry_failed_addresses(self, request, queryset):
        """Re-queue geocoding for failed addresses."""
        from .tasks import geocode_single_address

        count = 0
        for job in queryset:
            for error in job.errors.all():
                geocode_single_address.delay(
                    error.model_type,
                    str(error.model_id),
                    error.address_text,
                    str(job.pk),
                )
                error.retry_count += 1
                error.save(update_fields=["retry_count"])
                count += 1

        self.message_user(
            request,
            f"Queued {count} address(es) for retry.",
            messages.SUCCESS,
        )


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "district_type",
        "identifier",
        "state",
        "county",
        "effective_date",
    ]
    list_filter = ["district_type", "state"]
    search_fields = ["name", "identifier", "county"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "district_type", "identifier"]}),
        ("Location", {"fields": ["state", "county"]}),
        (
            "Boundary",
            {
                "fields": ["boundary", "source", "effective_date"],
                "classes": ["collapse"],
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]


# =============================================================================
# Stripe Connect Admin
# =============================================================================


@admin.register(StripeConnection)
class StripeConnectionAdmin(admin.ModelAdmin):
    list_display = [
        "owner_display",
        "stripe_user_id",
        "status",
        "livemode",
        "last_sync_at",
        "donation_count",
    ]
    list_filter = ["status", "livemode", "created_at"]
    search_fields = ["stripe_user_id", "candidate__name", "campaign__name"]
    readonly_fields = [
        "stripe_user_id",
        "stripe_publishable_key",
        "access_token_encrypted",
        "refresh_token_encrypted",
        "created_at",
        "updated_at",
        "last_sync_at",
    ]
    raw_id_fields = ["candidate", "campaign"]
    actions = ["trigger_sync", "deauthorize_connections"]
    fieldsets = [
        (None, {"fields": ["candidate", "campaign", "status"]}),
        (
            "Stripe Account",
            {
                "fields": [
                    "stripe_user_id",
                    "stripe_publishable_key",
                    "livemode",
                    "scope",
                ]
            },
        ),
        (
            "OAuth Tokens",
            {
                "fields": ["access_token_encrypted", "refresh_token_encrypted"],
                "classes": ["collapse"],
                "description": "Encrypted tokens - do not share or expose",
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at", "updated_at", "last_sync_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Owner")
    def owner_display(self, obj):
        owner = obj.owner
        if obj.candidate:
            return f"Candidate: {owner}"
        return f"Campaign: {owner}"

    @admin.display(description="Donations")
    def donation_count(self, obj):
        return obj.donations.count()

    @admin.action(description="Trigger donation sync")
    def trigger_sync(self, request, queryset):
        from civicpulse.tasks import sync_donations

        count = 0
        for conn in queryset.filter(status=StripeConnection.Status.ACTIVE):
            sync_donations.delay(str(conn.pk))
            count += 1
        self.message_user(
            request,
            f"Queued sync for {count} connection(s)",
            messages.SUCCESS,
        )

    @admin.action(description="Deauthorize selected connections")
    def deauthorize_connections(self, request, queryset):
        """Revoke access for selected Stripe connections."""
        count = 0
        for conn in queryset.filter(status=StripeConnection.Status.ACTIVE):
            conn.status = StripeConnection.Status.REVOKED
            conn.save(update_fields=["status", "updated_at"])
            count += 1
        self.message_user(
            request,
            f"Deauthorized {count} connection(s)",
            messages.SUCCESS,
        )


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = [
        "stripe_charge_id",
        "connection",
        "donor_name",
        "amount_display",
        "status",
        "charged_at",
    ]
    list_filter = ["status", "livemode", "charged_at"]
    search_fields = ["stripe_charge_id", "donor_name", "donor_email"]
    readonly_fields = [
        "stripe_charge_id",
        "stripe_payment_intent_id",
        "stripe_customer_id",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["connection"]
    date_hierarchy = "charged_at"
    fieldsets = [
        (None, {"fields": ["connection", "status"]}),
        (
            "Stripe IDs",
            {
                "fields": [
                    "stripe_charge_id",
                    "stripe_payment_intent_id",
                    "stripe_customer_id",
                ]
            },
        ),
        (
            "Amount",
            {
                "fields": ["amount_cents", "currency", "fee_cents", "net_cents"],
            },
        ),
        (
            "Donor Information",
            {
                "fields": ["donor_name", "donor_email"],
            },
        ),
        (
            "Details",
            {
                "fields": ["description", "receipt_url", "livemode"],
                "classes": ["collapse"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["charged_at", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Amount")
    def amount_display(self, obj):
        return f"${obj.amount_cents / 100:.2f}"


@admin.register(DonationSyncJob)
class DonationSyncJobAdmin(admin.ModelAdmin):
    list_display = [
        "connection",
        "status",
        "full_sync",
        "progress_display",
        "created_at",
        "completed_at",
    ]
    list_filter = ["status", "full_sync", "created_at"]
    readonly_fields = [
        "connection",
        "task_id",
        "total_charges",
        "processed_count",
        "created_count",
        "updated_count",
        "error_count",
        "error_messages",
        "created_at",
        "started_at",
        "completed_at",
    ]
    fieldsets = [
        (None, {"fields": ["connection", "status", "full_sync"]}),
        (
            "Progress",
            {
                "fields": [
                    "total_charges",
                    "processed_count",
                    "created_count",
                    "updated_count",
                    "error_count",
                ]
            },
        ),
        (
            "Errors",
            {
                "fields": ["error_messages"],
                "classes": ["collapse"],
            },
        ),
        (
            "Task Info",
            {
                "fields": ["task_id"],
                "classes": ["collapse"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at", "started_at", "completed_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Progress")
    def progress_display(self, obj):
        return f"{obj.processed_count}/{obj.total_charges} ({obj.progress_percentage}%)"
