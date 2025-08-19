"""
Django admin configuration for CivicPulse models.

This module provides comprehensive admin interface configuration for all models
including custom admin classes, list displays, filters, and inline editing.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html

from .models import ContactAttempt, Person, User, VoterRecord


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin configuration for User model."""

    # Fields to display in the list view
    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'role', 'organization', 'is_verified', 'is_active', 'date_joined'
    )

    # Fields to filter by
    list_filter = (
        'role', 'organization', 'is_verified', 'is_active',
        'is_staff', 'is_superuser', 'date_joined'
    )

    # Fields to search
    search_fields = ('username', 'email', 'first_name', 'last_name', 'organization')

    # Fields that can be edited directly in the list view
    list_editable = ('is_verified', 'is_active')

    # Number of items per page
    list_per_page = 25

    # Ordering
    ordering = ('-date_joined',)

    # Custom fieldsets for the form
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {
            'fields': ('role', 'organization', 'phone_number', 'is_verified'),
            'classes': ('wide',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('id', 'created_at', 'updated_at', 'date_joined', 'last_login')

    # Add custom fields to the add form
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Fields', {
            'fields': ('role', 'organization', 'phone_number', 'email'),
            'classes': ('wide',),
        }),
    )


class ContactAttemptInline(admin.TabularInline):
    """Inline admin for ContactAttempt within Person admin."""

    model = ContactAttempt
    extra = 0
    max_num = 10

    fields = (
        'contact_type', 'contact_date', 'result', 'sentiment',
        'contacted_by', 'follow_up_required', 'follow_up_date'
    )

    readonly_fields = ('created_at', 'updated_at')

    # Show only recent contact attempts by default
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('contacted_by').order_by('-contact_date')[:10]


class VoterRecordInline(admin.StackedInline):
    """Inline admin for VoterRecord within Person admin."""

    model = VoterRecord
    extra = 0
    max_num = 1

    fieldsets = (
        ('Registration Info', {
            'fields': (
                'voter_id', 'registration_date', 'registration_status',
                'party_affiliation'
            ),
        }),
        ('Districts & Location', {
            'fields': (
                'precinct', 'ward', 'congressional_district',
                'state_house_district', 'state_senate_district', 'polling_location'
            ),
            'classes': ('collapse',),
        }),
        ('Voting History', {
            'fields': ('last_voted_date', 'voter_score', 'voting_history'),
            'classes': ('collapse',),
        }),
        ('Absentee/Mail Voting', {
            'fields': (
                'absentee_voter', 'mail_ballot_requested',
                'mail_ballot_sent_date', 'mail_ballot_returned_date'
            ),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('source', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('created_at', 'updated_at')


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    """Custom admin configuration for Person model."""

    # Fields to display in the list view
    list_display = (
        'full_name', 'email', 'phone_primary', 'city', 'state',
        'has_voter_record', 'contact_count', 'created_at'
    )

    # Fields to filter by
    list_filter = (
        'state', 'gender', 'created_at', 'updated_at',
        'voter_record__registration_status', 'voter_record__party_affiliation'
    )

    # Fields to search
    search_fields = (
        'first_name', 'last_name', 'middle_name', 'email',
        'phone_primary', 'phone_secondary', 'street_address', 'city', 'zip_code'
    )

    # Number of items per page
    list_per_page = 25

    # Ordering
    ordering = ('last_name', 'first_name')

    # Custom fieldsets for the form
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'first_name', 'middle_name', 'last_name', 'suffix',
                'date_of_birth', 'gender'
            ),
        }),
        ('Contact Information', {
            'fields': ('email', 'phone_primary', 'phone_secondary'),
        }),
        ('Address', {
            'fields': (
                'street_address', 'apartment_number', 'city',
                'state', 'zip_code', 'county'
            ),
            'classes': ('collapse',),
        }),
        ('Additional Details', {
            'fields': ('occupation', 'employer', 'notes', 'tags'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('id', 'created_at', 'updated_at', 'full_name', 'age')

    # Include inlines for related models
    inlines = [VoterRecordInline, ContactAttemptInline]

    # Optimize queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('voter_record', 'created_by').prefetch_related(
            'contact_attempts'
        )

    # Custom methods for list display
    def has_voter_record(self, obj):
        """Display whether person has a voter record."""
        try:
            return obj.voter_record is not None
        except VoterRecord.DoesNotExist:
            return False
    has_voter_record.boolean = True
    has_voter_record.short_description = 'Voter Record'

    def contact_count(self, obj):
        """Display count of contact attempts."""
        count = obj.contact_attempts.count()
        if count > 0:
            url = reverse('admin:civicpulse_contactattempt_changelist')
            return format_html(
                '<a href="{}?person__id__exact={}">{} contacts</a>',
                url, obj.id, count
            )
        return '0 contacts'
    contact_count.short_description = 'Contacts'

    # Custom actions
    def mark_as_volunteers(self, request, queryset):
        """Mark selected persons as volunteers."""
        for person in queryset:
            if 'volunteer' not in person.tags:
                person.tags.append('volunteer')
                person.save()
        self.message_user(request, f'{queryset.count()} persons marked as volunteers.')
    mark_as_volunteers.short_description = 'Mark as volunteers'

    actions = ['mark_as_volunteers']


@admin.register(VoterRecord)
class VoterRecordAdmin(admin.ModelAdmin):
    """Custom admin configuration for VoterRecord model."""

    # Fields to display in the list view
    list_display = (
        'voter_id', 'person_link', 'registration_status', 'party_affiliation',
        'voter_score', 'voting_frequency', 'last_voted_date', 'precinct'
    )

    # Fields to filter by
    list_filter = (
        'registration_status', 'party_affiliation', 'precinct', 'ward',
        'congressional_district', 'absentee_voter', 'mail_ballot_requested',
        'created_at'
    )

    # Fields to search
    search_fields = (
        'voter_id', 'person__first_name', 'person__last_name',
        'person__email', 'precinct', 'ward', 'polling_location'
    )

    # Number of items per page
    list_per_page = 25

    # Ordering
    ordering = ('-voter_score', 'person__last_name')

    # Custom fieldsets for the form
    fieldsets = (
        ('Person', {
            'fields': ('person',),
        }),
        ('Registration Information', {
            'fields': (
                'voter_id', 'registration_date', 'registration_status',
                'party_affiliation'
            ),
        }),
        ('Voting Location', {
            'fields': (
                'precinct', 'ward', 'congressional_district',
                'state_house_district', 'state_senate_district', 'polling_location'
            ),
        }),
        ('Voting History', {
            'fields': ('voting_history', 'last_voted_date', 'voter_score'),
        }),
        ('Absentee/Mail Voting', {
            'fields': (
                'absentee_voter', 'mail_ballot_requested',
                'mail_ballot_sent_date', 'mail_ballot_returned_date'
            ),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('source', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('id', 'created_at', 'updated_at', 'voting_frequency')

    # Optimize queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('person')

    # Custom methods for list display
    def person_link(self, obj):
        """Display link to related person."""
        url = reverse('admin:civicpulse_person_change', args=[obj.person.id])
        return format_html('<a href="{}">{}</a>', url, obj.person.full_name)
    person_link.short_description = 'Person'

    # Custom actions
    def mark_high_priority(self, request, queryset):
        """Mark high-scoring voters for priority contact."""
        high_priority = queryset.filter(voter_score__gte=70)
        for voter in high_priority:
            person = voter.person
            if 'high_priority' not in person.tags:
                person.tags.append('high_priority')
                person.save()
        self.message_user(
            request, f'{high_priority.count()} high-priority voters marked.'
        )
    mark_high_priority.short_description = 'Mark high-priority voters'

    actions = ['mark_high_priority']


@admin.register(ContactAttempt)
class ContactAttemptAdmin(admin.ModelAdmin):
    """Custom admin configuration for ContactAttempt model."""

    # Fields to display in the list view
    list_display = (
        'person_link', 'contact_type', 'contact_date', 'result',
        'sentiment', 'contacted_by', 'follow_up_required', 'campaign'
    )

    # Fields to filter by
    list_filter = (
        'contact_type', 'result', 'sentiment', 'follow_up_required',
        'campaign', 'contacted_by', 'contact_date'
    )

    # Fields to search
    search_fields = (
        'person__first_name', 'person__last_name', 'person__email',
        'contacted_by__username', 'campaign', 'event', 'notes'
    )

    # Fields that can be edited directly in the list view
    list_editable = ('follow_up_required',)

    # Number of items per page
    list_per_page = 25

    # Ordering
    ordering = ('-contact_date',)

    # Custom fieldsets for the form
    fieldsets = (
        ('Contact Information', {
            'fields': ('person', 'contact_type', 'contact_date', 'contacted_by'),
        }),
        ('Result & Sentiment', {
            'fields': ('result', 'sentiment', 'duration_minutes'),
        }),
        ('Conversation Details', {
            'fields': ('issues_discussed', 'commitments', 'notes'),
            'classes': ('collapse',),
        }),
        ('Follow-up', {
            'fields': ('follow_up_required', 'follow_up_date'),
        }),
        ('Campaign/Event', {
            'fields': ('campaign', 'event'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = (
        'id', 'created_at', 'updated_at', 'was_successful', 'is_positive_sentiment'
    )

    # Optimize queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('person', 'contacted_by')

    # Custom methods for list display
    def person_link(self, obj):
        """Display link to related person."""
        url = reverse('admin:civicpulse_person_change', args=[obj.person.id])
        return format_html('<a href="{}">{}</a>', url, obj.person.full_name)
    person_link.short_description = 'Person'

    # Custom actions
    def mark_for_followup(self, request, queryset):
        """Mark selected contacts for follow-up."""
        from datetime import date, timedelta

        updated = queryset.update(
            follow_up_required=True,
            follow_up_date=date.today() + timedelta(days=7)
        )
        self.message_user(request, f'{updated} contacts marked for follow-up.')
    mark_for_followup.short_description = 'Mark for follow-up'

    def mark_positive_sentiment(self, request, queryset):
        """Mark contacts with positive sentiment for further engagement."""
        positive_contacts = queryset.filter(sentiment__in=['strong_support', 'support'])
        for contact in positive_contacts:
            person = contact.person
            if 'supporter' not in person.tags:
                person.tags.append('supporter')
                person.save()
        self.message_user(request, f'{positive_contacts.count()} supporters tagged.')
    mark_positive_sentiment.short_description = 'Tag positive sentiment as supporters'

    actions = ['mark_for_followup', 'mark_positive_sentiment']


# Admin site customization
admin.site.site_header = 'CivicPulse Administration'
admin.site.site_title = 'CivicPulse Admin'
admin.site.index_title = 'Welcome to CivicPulse Administration'
