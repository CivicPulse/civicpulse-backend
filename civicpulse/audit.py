"""
Audit trail system for tracking all system changes and user actions.

This module provides comprehensive audit logging functionality including:
- Model change tracking
- User authentication events
- Data import/export operations
- Search and filtering capabilities
"""

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, QuerySet
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser as User
else:
    User = get_user_model()


class AuditLogManager(models.Manager):
    """Custom manager for AuditLog with optimized queries and search capabilities."""

    def for_object(self, obj: models.Model) -> QuerySet:
        """Get audit logs for a specific object."""
        content_type = ContentType.objects.get_for_model(obj)
        return self.filter(content_type=content_type, object_id=str(obj.pk))

    def by_user(self, user: User) -> QuerySet:
        """Get audit logs for actions performed by a specific user."""
        return self.filter(user=user).select_related("user", "content_type")

    def by_date_range(self, start_date: datetime, end_date: datetime) -> QuerySet:
        """Get audit logs within a specific date range."""
        return self.filter(timestamp__range=(start_date, end_date))

    def by_action(self, action: str) -> QuerySet:
        """Get audit logs for a specific action type."""
        return self.filter(action=action).select_related("user", "content_type")

    def by_category(self, category: str) -> QuerySet:
        """Get audit logs for a specific category."""
        return self.filter(category=category).select_related("user", "content_type")

    def search(self, query: str) -> QuerySet:
        """
        Full-text search across audit logs.

        Searches in:
        - Object representation
        - Changes JSON
        - User information
        - Search vector field
        """
        return self.filter(
            Q(object_repr__icontains=query)
            | Q(search_vector__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
            | Q(changes__icontains=query)
        ).select_related("user", "content_type")

    def critical_events(self) -> QuerySet:
        """Get audit logs for critical security events."""
        return self.filter(severity="CRITICAL").select_related("user", "content_type")

    def recent_activity(self, hours: int = 24) -> QuerySet:
        """Get audit logs from the last N hours."""
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(timestamp__gte=cutoff).select_related("user", "content_type")


class AuditLog(models.Model):
    """
    Central audit log model for tracking all system changes and user actions.

    This model provides immutable audit trail records for compliance and security.
    """

    # Action type choices
    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"
    ACTION_SOFT_DELETE = "SOFT_DELETE"
    ACTION_RESTORE = "RESTORE"
    ACTION_LOGIN = "LOGIN"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_LOGIN_FAILED = "LOGIN_FAILED"
    ACTION_EXPORT = "EXPORT"
    ACTION_IMPORT = "IMPORT"
    ACTION_VIEW = "VIEW"
    ACTION_PERMISSION_CHANGE = "PERMISSION_CHANGE"
    ACTION_PASSWORD_CHANGE = "PASSWORD_CHANGE"  # nosec B105
    ACTION_PASSWORD_RESET = "PASSWORD_RESET"  # nosec B105

    ACTION_CHOICES = [
        (ACTION_CREATE, "Created"),
        (ACTION_UPDATE, "Updated"),
        (ACTION_DELETE, "Deleted"),
        (ACTION_SOFT_DELETE, "Soft Deleted"),
        (ACTION_RESTORE, "Restored"),
        (ACTION_LOGIN, "User Login"),
        (ACTION_LOGOUT, "User Logout"),
        (ACTION_LOGIN_FAILED, "Failed Login"),
        (ACTION_EXPORT, "Data Export"),
        (ACTION_IMPORT, "Data Import"),
        (ACTION_VIEW, "Viewed"),
        (ACTION_PERMISSION_CHANGE, "Permission Changed"),
        (ACTION_PASSWORD_CHANGE, "Password Changed"),
        (ACTION_PASSWORD_RESET, "Password Reset"),
    ]

    # Category choices
    CATEGORY_VOTER_DATA = "VOTER_DATA"
    CATEGORY_AUTH = "AUTH"
    CATEGORY_SYSTEM = "SYSTEM"
    CATEGORY_CONTACT = "CONTACT"
    CATEGORY_ADMIN = "ADMIN"
    CATEGORY_SECURITY = "SECURITY"

    CATEGORY_CHOICES = [
        (CATEGORY_VOTER_DATA, "Voter Data"),
        (CATEGORY_AUTH, "Authentication"),
        (CATEGORY_SYSTEM, "System"),
        (CATEGORY_CONTACT, "Contact Management"),
        (CATEGORY_ADMIN, "Administration"),
        (CATEGORY_SECURITY, "Security"),
    ]

    # Severity choices
    SEVERITY_INFO = "INFO"
    SEVERITY_WARNING = "WARNING"
    SEVERITY_ERROR = "ERROR"
    SEVERITY_CRITICAL = "CRITICAL"

    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Information"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_ERROR, "Error"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # User who performed the action
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    user_repr = models.CharField(
        max_length=255,
        blank=True,
        help_text="String representation of user at time of action",
    )

    # Action details
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_INFO
    )

    # Object that was affected (using Generic Foreign Key)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    # object_id must be nullable to match migration and allow system-level logs
    object_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)  # noqa: DJ001
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField(
        max_length=500, help_text="String representation of the affected object"
    )

    # Change tracking
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Field-by-field changes in format: {field: {'old': val, 'new': val}}",
    )
    old_values = models.JSONField(
        default=dict, null=True, blank=True, help_text="Complete old state of object"
    )
    new_values = models.JSONField(
        default=dict, null=True, blank=True, help_text="Complete new state of object"
    )

    # Request information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    # user_agent and session_key must be nullable to match migrations
    user_agent = models.CharField(max_length=500, blank=True, null=True)  # noqa: DJ001
    session_key = models.CharField(max_length=40, blank=True, null=True)  # noqa: DJ001

    # Additional context
    message = models.TextField(
        blank=True, help_text="Human-readable description of the action"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about the action (e.g., file names, counts)",
    )

    # Search optimization
    search_vector = models.TextField(
        blank=True, help_text="Concatenated searchable text for full-text search"
    )

    # Custom manager
    objects = AuditLogManager()

    class Meta:
        db_table = "audit_logs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["category", "-timestamp"]),
            models.Index(fields=["severity", "-timestamp"]),
            models.Index(fields=["ip_address"]),
        ]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        permissions = [
            ("export_auditlog", "Can export audit logs"),
            ("view_sensitive_auditlog", "Can view sensitive audit information"),
        ]

    def __str__(self) -> str:
        """String representation of the audit log entry."""
        user_display = self.user_repr or "System"
        return (
            f"{self.action} - {self.object_repr} by {user_display} at {self.timestamp}"
        )

    def save(self, *args, **kwargs):
        """
        Override save to ensure immutability and populate search fields.

        Audit logs should never be updated after creation.
        """
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Audit logs are immutable and cannot be modified")

        # Populate user representation
        if self.user and not self.user_repr:
            self.user_repr = str(self.user)

        # Build search vector for full-text search
        search_parts = [
            self.object_repr,
            self.user_repr or "",
            self.message,
            self.action,
            self.category,
        ]

        # Add change field names to search vector
        if self.changes:
            search_parts.extend(self.changes.keys())

        self.search_vector = " ".join(filter(None, search_parts))

        # Set severity based on action if not explicitly set
        if self.severity == self.SEVERITY_INFO:
            if self.action in [
                self.ACTION_DELETE,
                self.ACTION_PERMISSION_CHANGE,
                self.ACTION_PASSWORD_CHANGE,
            ]:
                self.severity = self.SEVERITY_WARNING
            elif self.action == self.ACTION_LOGIN_FAILED:
                self.severity = self.SEVERITY_WARNING
                # Multiple failed logins could escalate to CRITICAL

        super().save(*args, **kwargs)

    def get_changes_display(self) -> str:
        """Get a human-readable display of changes."""
        if not self.changes:
            return "No changes recorded"

        lines = []
        for field, change in self.changes.items():
            if isinstance(change, dict) and "old" in change and "new" in change:
                lines.append(f"{field}: {change['old']} → {change['new']}")
            else:
                lines.append(f"{field}: {change}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert audit log to dictionary for export."""
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user": self.user_repr,
            "action": self.get_action_display(),
            "category": self.get_category_display(),
            "severity": self.get_severity_display(),
            "object": self.object_repr,
            "changes": self.changes,
            "ip_address": self.ip_address,
            "message": self.message,
            "metadata": self.metadata,
        }

    @classmethod
    def log_action(
        cls,
        action: str,
        user: User | None = None,
        obj: models.Model | None = None,
        changes: dict | None = None,
        message: str = "",
        category: str = CATEGORY_SYSTEM,
        severity: str = SEVERITY_INFO,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict | None = None,
    ) -> "AuditLog":
        """
        Convenience method to create an audit log entry.

        Args:
            action: The action type (from ACTION_CHOICES)
            user: The user performing the action
            obj: The object being affected
            changes: Dictionary of field changes
            message: Human-readable message
            category: Category of the action
            severity: Severity level
            ip_address: IP address of the request
            user_agent: User agent string
            metadata: Additional metadata

        Returns:
            The created AuditLog instance
        """
        audit_log = cls(
            user=cast(Any, user),
            action=action,
            category=category,
            severity=severity,
            changes=changes or {},
            message=message,
            ip_address=ip_address,
            user_agent=user_agent or "",
            metadata=metadata or {},
        )

        if obj:
            audit_log.content_type = ContentType.objects.get_for_model(obj)
            audit_log.object_id = str(obj.pk)
            audit_log.object_repr = str(obj)

        audit_log.save()
        return audit_log


class AuditMixin(models.Model):
    """
    Mixin class to add audit logging capabilities to models.

    Add this to any model that needs automatic audit logging:

    class MyModel(AuditMixin, models.Model):
        ...
    """

    class Meta:
        abstract = True

    # Override these in your model if needed
    audit_category = AuditLog.CATEGORY_SYSTEM
    audit_exclude_fields = [
        "updated_at",
        "search_vector",
    ]  # Fields to exclude from change tracking

    def get_audit_changes(self, old_instance: models.Model | None = None) -> dict:
        """
        Get the changes between this instance and an old instance.

        Args:
            old_instance: The previous state of the model

        Returns:
            Dictionary of changes
        """
        if not old_instance:
            return {}

        changes = {}
        for field in self._meta.fields:
            if field.name in self.audit_exclude_fields:
                continue

            old_value = getattr(old_instance, field.name)
            new_value = getattr(self, field.name)

            # Handle special field types
            if hasattr(old_value, "isoformat"):  # DateTime fields
                old_value = old_value.isoformat() if old_value else None
                new_value = new_value.isoformat() if new_value else None
            elif isinstance(field, models.ForeignKey):  # Foreign keys
                old_value = str(old_value) if old_value else None
                new_value = str(new_value) if new_value else None
            else:
                old_value = str(old_value) if old_value is not None else None
                new_value = str(new_value) if new_value is not None else None

            if old_value != new_value:
                changes[field.name] = {"old": old_value, "new": new_value}

        return changes

    def create_audit_log(
        self,
        action: str,
        user: User | None = None,
        changes: dict | None = None,
        message: str = "",
        **kwargs,
    ) -> AuditLog:
        """
        Create an audit log entry for this model instance.

        Args:
            action: The action being performed
            user: The user performing the action
            changes: The changes being made
            message: Optional message
            **kwargs: Additional arguments for AuditLog

        Returns:
            The created AuditLog instance
        """
        return AuditLog.log_action(
            action=action,
            user=user,
            obj=self,
            changes=changes,
            message=message,
            category=kwargs.get("category", self.audit_category),
            **kwargs,
        )
