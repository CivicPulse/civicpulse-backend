from django.contrib import admin

from .models import (
    Address,
    Candidate,
    ContactAttempt,
    ContactEffort,
    EffortAssignment,
    Election,
    ElectionDate,
    Email,
    Office,
    Person,
    PhoneNumber,
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
    ]
    list_filter = ["election_type", "status", "year", "office__level", "office__state"]
    search_fields = ["office__name", "office__city", "description"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["office", "parent_election"]
    inlines = [CandidateInline, ElectionDateInline]
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
        "election",
        "candidate",
        "assignment_count",
        "created_by",
        "created_at",
    ]
    list_filter = ["is_active", "election__year", "created_at"]
    search_fields = ["name", "description", "election__office__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["election", "candidate"]
    inlines = [EffortAssignmentInline]
    fieldsets = [
        (None, {"fields": ["name", "description", "is_active"]}),
        ("Script", {"fields": ["script"]}),
        (
            "Election Association",
            {
                "fields": ["election", "candidate"],
                "classes": ["collapse"],
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
