"""
Django admin configuration for CivicPulse models.

This module provides comprehensive admin interface configuration for all models
including custom admin classes, list displays, filters, and inline editing.
"""

from datetime import timedelta

from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .audit import AuditLog
from .models import Campaign, ContactAttempt, Person, User, VoterRecord


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin configuration for User model."""

    # Fields to display in the list view
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "organization",
        "is_verified",
        "is_active",
        "date_joined",
    )

    # Fields to filter by
    list_filter = (
        "role",
        "organization",
        "is_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    )

    # Fields to search
    search_fields = ("username", "email", "first_name", "last_name", "organization")

    # Fields that can be edited directly in the list view
    list_editable = ("is_verified", "is_active")

    # Number of items per page
    list_per_page = 25

    # Ordering
    ordering = ("-date_joined",)

    # Custom fieldsets for the form
    fieldsets = list(BaseUserAdmin.fieldsets or ()) + [
        (
            "Custom Fields",
            {
                "fields": ("role", "organization", "phone_number", "is_verified"),
                "classes": ("wide",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    ]

    readonly_fields = ("id", "created_at", "updated_at", "date_joined", "last_login")

    # Add custom fields to the add form
    add_fieldsets = list(BaseUserAdmin.add_fieldsets or ()) + [
        (
            "Custom Fields",
            {
                "fields": ("role", "organization", "phone_number", "email"),
                "classes": ("wide",),
            },
        ),
    ]


class ContactAttemptInline(admin.TabularInline):
    """Inline admin for ContactAttempt within Person admin."""

    model = ContactAttempt
    extra = 0
    max_num = 10

    fields = (
        "contact_type",
        "contact_date",
        "result",
        "sentiment",
        "contacted_by",
        "follow_up_required",
        "follow_up_date",
    )

    readonly_fields = ("created_at", "updated_at")

    # Show only recent contact attempts by default
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("contacted_by").order_by("-contact_date")[:10]


class VoterRecordInline(admin.StackedInline):
    """Inline admin for VoterRecord within Person admin."""

    model = VoterRecord
    extra = 0
    max_num = 1

    fieldsets = (
        (
            "Registration Info",
            {
                "fields": (
                    "voter_id",
                    "registration_date",
                    "registration_status",
                    "party_affiliation",
                ),
            },
        ),
        (
            "Districts & Location",
            {
                "fields": (
                    "precinct",
                    "ward",
                    "congressional_district",
                    "state_house_district",
                    "state_senate_district",
                    "polling_location",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Voting History",
            {
                "fields": ("last_voted_date", "voter_score", "voting_history"),
                "classes": ("collapse",),
            },
        ),
        (
            "Absentee/Mail Voting",
            {
                "fields": (
                    "absentee_voter",
                    "mail_ballot_requested",
                    "mail_ballot_sent_date",
                    "mail_ballot_returned_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("source", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("created_at", "updated_at")


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    """Custom admin configuration for Person model."""

    # Fields to display in the list view
    list_display = (
        "full_name",
        "email",
        "phone_primary",
        "city",
        "state",
        "has_voter_record",
        "contact_count",
        "created_at",
    )

    # Fields to filter by
    list_filter = (
        "state",
        "gender",
        "created_at",
        "updated_at",
        "voter_record__registration_status",
        "voter_record__party_affiliation",
    )

    # Fields to search
    search_fields = (
        "first_name",
        "last_name",
        "middle_name",
        "email",
        "phone_primary",
        "phone_secondary",
        "street_address",
        "city",
        "zip_code",
    )

    # Number of items per page
    list_per_page = 25

    # Ordering
    ordering = ("last_name", "first_name")

    # Custom fieldsets for the form
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "first_name",
                    "middle_name",
                    "last_name",
                    "suffix",
                    "date_of_birth",
                    "gender",
                ),
            },
        ),
        (
            "Contact Information",
            {
                "fields": ("email", "phone_primary", "phone_secondary"),
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "street_address",
                    "apartment_number",
                    "city",
                    "state",
                    "zip_code",
                    "county",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Additional Details",
            {
                "fields": ("occupation", "employer", "notes", "tags"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("id", "created_at", "updated_at", "full_name", "age")

    # Include inlines for related models
    inlines = [VoterRecordInline, ContactAttemptInline]

    # Optimize queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("voter_record", "created_by").prefetch_related(
            "contact_attempts"
        )

    # Custom methods for list display
    @admin.display(boolean=True, description="Voter Record")
    def has_voter_record(self, obj):
        """Display whether person has a voter record."""
        try:
            return obj.voter_record is not None
        except VoterRecord.DoesNotExist:
            return False

    @admin.display(description="Contacts")
    def contact_count(self, obj):
        """Display count of contact attempts."""
        count = obj.contact_attempts.count()
        if count > 0:
            url = reverse("admin:civicpulse_contactattempt_changelist")
            return format_html(
                '<a href="{}?person__id__exact={}">{} contacts</a>', url, obj.id, count
            )
        return "0 contacts"

    # Custom actions
    @admin.action(description="Mark as volunteers")
    def mark_as_volunteers(self, request, queryset):
        """Mark selected persons as volunteers."""
        for person in queryset:
            if "volunteer" not in person.tags:
                person.tags.append("volunteer")
                person.save()
        self.message_user(request, f"{queryset.count()} persons marked as volunteers.")

    actions = ["mark_as_volunteers"]


@admin.register(VoterRecord)
class VoterRecordAdmin(admin.ModelAdmin):
    """Custom admin configuration for VoterRecord model."""

    # Fields to display in the list view
    list_display = (
        "voter_id",
        "person_link",
        "registration_status",
        "party_affiliation",
        "voter_score",
        "voting_frequency",
        "last_voted_date",
        "precinct",
    )

    # Fields to filter by
    list_filter = (
        "registration_status",
        "party_affiliation",
        "precinct",
        "ward",
        "congressional_district",
        "absentee_voter",
        "mail_ballot_requested",
        "created_at",
    )

    # Fields to search
    search_fields = (
        "voter_id",
        "person__first_name",
        "person__last_name",
        "person__email",
        "precinct",
        "ward",
        "polling_location",
    )

    # Number of items per page
    list_per_page = 25

    # Ordering
    ordering = ("-voter_score", "person__last_name")

    # Custom fieldsets for the form
    fieldsets = (
        (
            "Person",
            {
                "fields": ("person",),
            },
        ),
        (
            "Registration Information",
            {
                "fields": (
                    "voter_id",
                    "registration_date",
                    "registration_status",
                    "party_affiliation",
                ),
            },
        ),
        (
            "Voting Location",
            {
                "fields": (
                    "precinct",
                    "ward",
                    "congressional_district",
                    "state_house_district",
                    "state_senate_district",
                    "polling_location",
                ),
            },
        ),
        (
            "Voting History",
            {
                "fields": ("voting_history", "last_voted_date", "voter_score"),
            },
        ),
        (
            "Absentee/Mail Voting",
            {
                "fields": (
                    "absentee_voter",
                    "mail_ballot_requested",
                    "mail_ballot_sent_date",
                    "mail_ballot_returned_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("source", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ("id", "created_at", "updated_at", "voting_frequency")

    # Optimize queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("person")

    # Custom methods for list display
    @admin.display(description="Person")
    def person_link(self, obj):
        """Display link to related person."""
        url = reverse("admin:civicpulse_person_change", args=[obj.person.id])
        return format_html('<a href="{}">{}</a>', url, obj.person.full_name)

    # Custom actions
    @admin.action(description="Mark high-priority voters")
    def mark_high_priority(self, request, queryset):
        """Mark high-scoring voters for priority contact."""
        high_priority = queryset.filter(voter_score__gte=70)
        for voter in high_priority:
            person = voter.person
            if "high_priority" not in person.tags:
                person.tags.append("high_priority")
                person.save()
        self.message_user(
            request, f"{high_priority.count()} high-priority voters marked."
        )

    actions = ["mark_high_priority"]


@admin.register(ContactAttempt)
class ContactAttemptAdmin(admin.ModelAdmin):
    """Custom admin configuration for ContactAttempt model."""

    # Fields to display in the list view
    list_display = (
        "person_link",
        "contact_type",
        "contact_date",
        "result",
        "sentiment",
        "contacted_by",
        "follow_up_required",
        "campaign",
    )

    # Fields to filter by
    list_filter = (
        "contact_type",
        "result",
        "sentiment",
        "follow_up_required",
        "campaign",
        "contacted_by",
        "contact_date",
    )

    # Fields to search
    search_fields = (
        "person__first_name",
        "person__last_name",
        "person__email",
        "contacted_by__username",
        "campaign",
        "event",
        "notes",
    )

    # Fields that can be edited directly in the list view
    list_editable = ("follow_up_required",)

    # Number of items per page
    list_per_page = 25

    # Ordering
    ordering = ("-contact_date",)

    # Custom fieldsets for the form
    fieldsets = (
        (
            "Contact Information",
            {
                "fields": ("person", "contact_type", "contact_date", "contacted_by"),
            },
        ),
        (
            "Result & Sentiment",
            {
                "fields": ("result", "sentiment", "duration_minutes"),
            },
        ),
        (
            "Conversation Details",
            {
                "fields": ("issues_discussed", "commitments", "notes"),
                "classes": ("collapse",),
            },
        ),
        (
            "Follow-up",
            {
                "fields": ("follow_up_required", "follow_up_date"),
            },
        ),
        (
            "Campaign/Event",
            {
                "fields": ("campaign", "event"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "was_successful",
        "is_positive_sentiment",
    )

    # Optimize queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("person", "contacted_by")

    # Custom methods for list display
    @admin.display(description="Person")
    def person_link(self, obj):
        """Display link to related person."""
        url = reverse("admin:civicpulse_person_change", args=[obj.person.id])
        return format_html('<a href="{}">{}</a>', url, obj.person.full_name)

    # Custom actions
    @admin.action(description="Mark for follow-up")
    def mark_for_followup(self, request, queryset):
        """Mark selected contacts for follow-up."""
        from datetime import date, timedelta

        updated = queryset.update(
            follow_up_required=True, follow_up_date=date.today() + timedelta(days=7)
        )
        self.message_user(request, f"{updated} contacts marked for follow-up.")

    @admin.action(description="Tag positive sentiment as supporters")
    def mark_positive_sentiment(self, request, queryset):
        """Mark contacts with positive sentiment for further engagement."""
        positive_contacts = queryset.filter(sentiment__in=["strong_support", "support"])
        for contact in positive_contacts:
            person = contact.person
            if "supporter" not in person.tags:
                person.tags.append("supporter")
                person.save()
        self.message_user(request, f"{positive_contacts.count()} supporters tagged.")

    actions = ["mark_for_followup", "mark_positive_sentiment"]


class CampaignContactAttemptInline(admin.TabularInline):
    """Inline admin for ContactAttempt within Campaign admin."""

    model = ContactAttempt
    extra = 1
    can_delete = True

    fields = (
        "contact_type",
        "contact_date",
        "result",
        "notes",
        "contacted_by",
    )

    readonly_fields = ("contacted_by", "created_at")
    ordering = ["-contact_date"]

    # Show only recent contact attempts by default
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("contacted_by", "person").order_by("-contact_date")


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """Custom admin configuration for Campaign model."""

    # Fields to display in the list view
    list_display = (
        "name",
        "candidate_name",
        "election_date",
        "status",
        "days_until_election_display",
        "created_by",
        "created_at",
    )

    # Fields to filter by
    list_filter = (
        "status",
        "election_date",
        "created_at",
        "organization",
    )

    # Fields to search
    search_fields = (
        "name",
        "candidate_name",
        "description",
        "organization",
    )

    # Number of items per page
    list_per_page = 25

    # Ordering
    ordering = ["-created_at"]

    # Date hierarchy navigation
    date_hierarchy = "election_date"

    # Custom fieldsets for the form
    fieldsets = (
        (
            "Campaign Information",
            {
                "fields": (
                    "name",
                    "candidate_name",
                    "election_date",
                    "status",
                ),
            },
        ),
        (
            "Details",
            {
                "fields": ("description", "organization"),
            },
        ),
        (
            "Audit Information",
            {
                "fields": (
                    "id",
                    "created_by",
                    "created_at",
                    "updated_at",
                    "is_active",
                    "deleted_at",
                    "deleted_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "created_by",
        "deleted_at",
        "deleted_by",
        "days_until_election_display",
    )

    # Include inlines for related models
    inlines = [CampaignContactAttemptInline]

    # Optimize queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("created_by", "deleted_by").prefetch_related(
            "contact_attempts"
        )

    # Custom methods for list display
    @admin.display(description="Days Until Election", ordering="election_date")
    def days_until_election_display(self, obj):
        """Display days until election with color coding."""
        days = obj.days_until_election
        if days is None:
            # Election has passed
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                "red",
                "Past Election",
            )
        elif days == 0:
            return format_html(
                '<span style="color: orange; font-weight: bold;">Today!</span>'
            )
        elif days <= 30:
            return format_html(
                '<span style="color: orange; font-weight: bold;">{} days</span>', days
            )
        else:
            return format_html('<span style="color: green;">{} days</span>', days)

    # Override save_model to set created_by on creation
    def save_model(self, request, obj, form, change):
        """Set created_by on creation."""
        if not change:  # Only on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # Custom actions
    @admin.action(description="Archive selected campaigns")
    def archive_campaigns(self, request, queryset):
        """Set status to archived for selected campaigns."""
        updated = queryset.update(status="archived")
        self.message_user(request, f"{updated} campaign(s) successfully archived.")

    @admin.action(description="Activate selected campaigns")
    def activate_campaigns(self, request, queryset):
        """Set status to active for selected campaigns."""
        updated = queryset.update(status="active")
        self.message_user(request, f"{updated} campaign(s) successfully activated.")

    @admin.action(description="Export selected campaigns to CSV")
    def export_to_csv(self, request, queryset):
        """Export selected campaigns to CSV."""
        import csv

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="campaigns.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "ID",
                "Name",
                "Candidate Name",
                "Election Date",
                "Status",
                "Organization",
                "Days Until Election",
                "Created By",
                "Created At",
                "Description",
            ]
        )

        for campaign in queryset:
            election_date_str = (
                campaign.election_date.isoformat() if campaign.election_date else ""
            )
            days_until = (
                campaign.days_until_election
                if campaign.days_until_election is not None
                else "Past"
            )
            created_by_str = (
                campaign.created_by.username if campaign.created_by else "Unknown"
            )
            created_at_str = (
                campaign.created_at.isoformat() if campaign.created_at else ""
            )

            writer.writerow(
                [
                    str(campaign.id),
                    campaign.name,
                    campaign.candidate_name,
                    election_date_str,
                    campaign.status,
                    campaign.organization,
                    days_until,
                    created_by_str,
                    created_at_str,
                    campaign.description,
                ]
            )

        # Log the export action
        AuditLog.log_action(
            action=AuditLog.ACTION_EXPORT,
            user=request.user,
            message=f"Exported {queryset.count()} campaign(s) to CSV",
            category=AuditLog.CATEGORY_ADMIN,
            severity=AuditLog.SEVERITY_INFO,
            metadata={
                "export_type": "campaigns",
                "format": "csv",
                "record_count": queryset.count(),
            },
        )

        return response

    actions = ["archive_campaigns", "activate_campaigns", "export_to_csv"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for AuditLog model.

    Provides read-only access to audit logs with comprehensive
    search and filtering capabilities.
    """

    # Fields to display in the list view
    list_display = (
        "timestamp",
        "action_display",
        "user_link",
        "object_display",
        "category_badge",
        "severity_badge",
        "ip_address",
        "changes_summary",
    )

    # Fields to filter by
    list_filter = (
        "action",
        "category",
        "severity",
        ("timestamp", DateFieldListFilter),
        ("user", admin.RelatedOnlyFieldListFilter),
        ("content_type", admin.RelatedOnlyFieldListFilter),
    )

    # Fields to search
    search_fields = (
        "object_repr",
        "user_repr",
        "message",
        "search_vector",
        "ip_address",
        "user__username",
        "user__email",
    )

    # Search help text
    search_help_text = (
        "Search across object names, users, messages, IP addresses, and changes. "
        "Try searching for usernames, email addresses, or specific actions."
    )

    # Number of items per page
    list_per_page = 50

    # Ordering
    ordering = ("-timestamp",)

    # Date hierarchy navigation
    date_hierarchy = "timestamp"

    # Read-only - audit logs should never be edited
    readonly_fields = [field.name for field in AuditLog._meta.fields]

    # Custom fieldsets for the form
    fieldsets = (
        (
            "Event Information",
            {
                "fields": (
                    "timestamp",
                    "action",
                    "category",
                    "severity",
                    "message",
                ),
            },
        ),
        (
            "User Information",
            {
                "fields": (
                    "user",
                    "user_repr",
                    "ip_address",
                    "user_agent",
                    "session_key",
                ),
            },
        ),
        (
            "Object Information",
            {
                "fields": (
                    "content_type",
                    "object_id",
                    "object_repr",
                ),
            },
        ),
        (
            "Change Details",
            {
                "fields": (
                    "changes",
                    "old_values",
                    "new_values",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Additional Data",
            {
                "fields": (
                    "metadata",
                    "search_vector",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # Prevent any modifications
    def has_add_permission(self, request):
        """Audit logs cannot be manually created."""
        return False

    def has_change_permission(self, request, obj=None):
        """Audit logs cannot be edited."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Audit logs cannot be deleted."""
        return False

    # Optimize queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "content_type").prefetch_related(
            "content_object"
        )

    # Custom display methods
    @admin.display(description="Action", ordering="action")
    def action_display(self, obj):
        """Display action with color coding."""
        color_map = {
            AuditLog.ACTION_CREATE: "green",
            AuditLog.ACTION_UPDATE: "blue",
            AuditLog.ACTION_DELETE: "red",
            AuditLog.ACTION_SOFT_DELETE: "orange",
            AuditLog.ACTION_LOGIN: "teal",
            AuditLog.ACTION_LOGOUT: "gray",
            AuditLog.ACTION_LOGIN_FAILED: "red",
            AuditLog.ACTION_EXPORT: "purple",
            AuditLog.ACTION_IMPORT: "purple",
        }
        color = color_map.get(obj.action, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_action_display(),
        )

    @admin.display(description="User", ordering="user")
    def user_link(self, obj):
        """Display link to user if available."""
        if obj.user:
            url = reverse("admin:civicpulse_user_change", args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user_repr or obj.user)
        return obj.user_repr or "System"

    @admin.display(description="Object", ordering="object_repr")
    def object_display(self, obj):
        """Display affected object with link if possible."""
        if obj.content_type and obj.object_id:
            try:
                # Try to create admin link
                app_label = obj.content_type.app_label
                model_name = obj.content_type.model
                url = reverse(
                    f"admin:{app_label}_{model_name}_change", args=[obj.object_id]
                )
                return format_html('<a href="{}">{}</a>', url, obj.object_repr)
            except Exception:  # nosec B110
                # Fallback to text if link can't be created
                pass
        return obj.object_repr or "-"

    @admin.display(description="Category")
    def category_badge(self, obj):
        """Display category as a colored badge."""
        color_map = {
            AuditLog.CATEGORY_VOTER_DATA: "#2E7D32",
            AuditLog.CATEGORY_AUTH: "#1565C0",
            AuditLog.CATEGORY_SYSTEM: "#616161",
            AuditLog.CATEGORY_CONTACT: "#00838F",
            AuditLog.CATEGORY_ADMIN: "#6A1B9A",
            AuditLog.CATEGORY_SECURITY: "#C62828",
        }
        color = color_map.get(obj.category, "#424242")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_category_display(),
        )

    @admin.display(description="Severity")
    def severity_badge(self, obj):
        """Display severity as a colored badge."""
        color_map = {
            AuditLog.SEVERITY_INFO: "#90A4AE",
            AuditLog.SEVERITY_WARNING: "#FFA726",
            AuditLog.SEVERITY_ERROR: "#EF5350",
            AuditLog.SEVERITY_CRITICAL: "#E53935",
        }
        color = color_map.get(obj.severity, "#90A4AE")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_severity_display(),
        )

    @admin.display(description="Changes")
    def changes_summary(self, obj):
        """Display summary of changes."""
        if not obj.changes:
            return "-"

        change_count = len(obj.changes)
        if change_count == 1:
            field = list(obj.changes.keys())[0]
            return f"{field} changed"
        else:
            return f"{change_count} fields changed"

    # Custom actions
    @admin.action(description="Export selected audit logs to CSV")
    def export_to_csv(self, request, queryset):
        """Export selected audit logs to CSV."""
        import csv

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit_logs.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Timestamp",
                "User",
                "Action",
                "Category",
                "Severity",
                "Object",
                "IP Address",
                "Message",
                "Changes",
            ]
        )

        for log in queryset:
            writer.writerow(
                [
                    log.timestamp.isoformat() if log.timestamp else "",
                    log.user_repr or "System",
                    log.get_action_display(),
                    log.get_category_display(),
                    log.get_severity_display(),
                    log.object_repr,
                    log.ip_address or "",
                    log.message,
                    log.get_changes_display() if log.changes else "",
                ]
            )

        # Log the export action
        AuditLog.log_action(
            action=AuditLog.ACTION_EXPORT,
            user=request.user,
            message=f"Exported {queryset.count()} audit log entries to CSV",
            category=AuditLog.CATEGORY_ADMIN,
            severity=AuditLog.SEVERITY_WARNING,
            metadata={
                "export_type": "audit_logs",
                "format": "csv",
                "record_count": queryset.count(),
            },
        )

        return response

    @admin.action(description="Generate audit report for selected logs")
    def generate_report(self, request, queryset):
        """Generate a summary report of selected audit logs."""
        from django.db.models import Count

        # Get statistics
        stats = {
            "total_events": queryset.count(),
            "date_range": {
                "start": queryset.last().timestamp if queryset.exists() else None,
                "end": queryset.first().timestamp if queryset.exists() else None,
            },
            "by_action": dict(
                queryset.values_list("action").annotate(Count("id")).order_by()
            ),
            "by_category": dict(
                queryset.values_list("category").annotate(Count("id")).order_by()
            ),
            "by_severity": dict(
                queryset.values_list("severity").annotate(Count("id")).order_by()
            ),
            "unique_users": queryset.values("user").distinct().count(),
            "unique_ips": queryset.values("ip_address").distinct().count(),
        }

        # Create report content
        report_lines = [
            "AUDIT LOG REPORT",
            "=" * 50,
            f"Generated: {timezone.now().isoformat()}",
            f"Generated by: {request.user}",
            "",
            "SUMMARY",
            "-" * 30,
            f"Total Events: {stats['total_events']}",
            (
                f"Date Range: {stats['date_range']['start']} to "
                f"{stats['date_range']['end']}"
            ),
            f"Unique Users: {stats['unique_users']}",
            f"Unique IPs: {stats['unique_ips']}",
            "",
            "EVENTS BY ACTION",
            "-" * 30,
        ]

        for action, count in stats["by_action"].items():
            action_display = dict(AuditLog.ACTION_CHOICES).get(action, action)
            report_lines.append(f"{action_display}: {count}")

        report_lines.extend(
            [
                "",
                "EVENTS BY CATEGORY",
                "-" * 30,
            ]
        )

        for category, count in stats["by_category"].items():
            category_display = dict(AuditLog.CATEGORY_CHOICES).get(category, category)
            report_lines.append(f"{category_display}: {count}")

        report_lines.extend(
            [
                "",
                "EVENTS BY SEVERITY",
                "-" * 30,
            ]
        )

        for severity, count in stats["by_severity"].items():
            severity_display = dict(AuditLog.SEVERITY_CHOICES).get(severity, severity)
            report_lines.append(f"{severity_display}: {count}")

        # Return as text file
        response = HttpResponse(content_type="text/plain")
        response["Content-Disposition"] = 'attachment; filename="audit_report.txt"'
        response.write("\n".join(report_lines))

        # Log the report generation
        AuditLog.log_action(
            action=AuditLog.ACTION_EXPORT,
            user=request.user,
            message=f"Generated audit report for {queryset.count()} entries",
            category=AuditLog.CATEGORY_ADMIN,
            severity=AuditLog.SEVERITY_INFO,
            metadata={
                "export_type": "audit_report",
                "format": "txt",
                "record_count": queryset.count(),
                "stats": stats,
            },
        )

        return response

    @admin.action(description="Generate security summary report")
    def generate_security_report(self, request, queryset):
        """Generate a focused security report from selected audit logs."""
        from django.db.models import Count

        # Filter for security-related events
        security_logs = queryset.filter(
            category__in=[
                AuditLog.CATEGORY_SECURITY,
                AuditLog.CATEGORY_AUTH,
            ]
        )

        # Get statistics
        stats = {
            "total_events": security_logs.count(),
            "date_range": {
                "start": (
                    security_logs.last().timestamp if security_logs.exists() else None
                ),
                "end": (
                    security_logs.first().timestamp if security_logs.exists() else None
                ),
            },
            "failed_logins": security_logs.filter(
                action=AuditLog.ACTION_LOGIN_FAILED
            ).count(),
            "critical_events": security_logs.filter(
                severity=AuditLog.SEVERITY_CRITICAL
            ).count(),
            "unique_ips": security_logs.values("ip_address").distinct().count(),
            "by_action": dict(
                security_logs.values_list("action").annotate(Count("id")).order_by()
            ),
            "by_severity": dict(
                security_logs.values_list("severity").annotate(Count("id")).order_by()
            ),
        }

        # Create report content
        report_lines = [
            "SECURITY AUDIT REPORT",
            "=" * 50,
            f"Generated: {timezone.now().isoformat()}",
            f"Generated by: {request.user}",
            f"Report covers: {stats['total_events']} security-related events",
            "",
            "SECURITY SUMMARY",
            "-" * 30,
            f"Failed Logins: {stats['failed_logins']}",
            f"Critical Events: {stats['critical_events']}",
            f"Unique IP Addresses: {stats['unique_ips']}",
            (
                f"Date Range: {stats['date_range']['start']} to "
                f"{stats['date_range']['end']}"
            ),
            "",
            "SECURITY EVENTS BY TYPE",
            "-" * 30,
        ]

        for action, count in stats["by_action"].items():
            action_display = dict(AuditLog.ACTION_CHOICES).get(action, action)
            report_lines.append(f"{action_display}: {count}")

        report_lines.extend(
            [
                "",
                "EVENTS BY SEVERITY",
                "-" * 30,
            ]
        )

        for severity, count in stats["by_severity"].items():
            severity_display = dict(AuditLog.SEVERITY_CHOICES).get(severity, severity)
            report_lines.append(f"{severity_display}: {count}")

        # Add recommendations
        report_lines.extend(
            [
                "",
                "SECURITY RECOMMENDATIONS",
                "-" * 30,
            ]
        )

        if stats["failed_logins"] > 10:
            report_lines.append(
                "⚠ High number of failed logins detected - review authentication logs"
            )
        if stats["critical_events"] > 0:
            report_lines.append(
                "🚨 Critical security events require immediate attention"
            )
        if stats["unique_ips"] > 50:
            report_lines.append(
                "ℹ High number of unique IPs - monitor for suspicious activity"
            )

        if not any([stats["failed_logins"] > 10, stats["critical_events"] > 0]):
            report_lines.append("✓ No immediate security concerns detected")

        # Return as text file
        response = HttpResponse(content_type="text/plain")
        response["Content-Disposition"] = (
            'attachment; filename="security_audit_report.txt"'
        )
        response.write("\n".join(report_lines))

        # Log the report generation
        AuditLog.log_action(
            action=AuditLog.ACTION_EXPORT,
            user=request.user,
            message=(
                f"Generated security audit report for {security_logs.count()} entries"
            ),
            category=AuditLog.CATEGORY_ADMIN,
            severity=AuditLog.SEVERITY_INFO,
            metadata={
                "export_type": "security_audit_report",
                "format": "txt",
                "record_count": security_logs.count(),
                "stats": stats,
            },
        )

        return response

    actions = ["export_to_csv", "generate_report", "generate_security_report"]

    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to the changelist view."""
        extra_context = extra_context or {}

        # Get recent statistics
        recent_cutoff = timezone.now() - timedelta(hours=24)
        recent_logs = AuditLog.objects.filter(timestamp__gte=recent_cutoff)

        extra_context["audit_stats"] = {
            "total_logs": AuditLog.objects.count(),
            "recent_24h": recent_logs.count(),
            "critical_events": AuditLog.objects.filter(
                severity=AuditLog.SEVERITY_CRITICAL
            ).count(),
            "failed_logins": AuditLog.objects.filter(
                action=AuditLog.ACTION_LOGIN_FAILED, timestamp__gte=recent_cutoff
            ).count(),
        }

        return super().changelist_view(request, extra_context=extra_context)


# Admin site customization
admin.site.site_header = "CivicPulse Administration"
admin.site.site_title = "CivicPulse Admin"
admin.site.index_title = "Welcome to CivicPulse Administration"
