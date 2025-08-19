"""
Signal handlers for automatic audit trail logging.

This module provides Django signal handlers that automatically create
audit log entries for model changes and authentication events.
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models import Model
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from civicpulse.audit import AuditLog
from civicpulse.middleware.audit import get_request_audit_context
from civicpulse.middleware.current_user import get_current_user
from civicpulse.models import ContactAttempt, Person, VoterRecord

logger = logging.getLogger(__name__)
User = get_user_model()


# Models to automatically audit
AUDITED_MODELS = [Person, VoterRecord, ContactAttempt, User]


def get_model_changes(instance: Model, created: bool = False) -> dict:
    """
    Get the changes made to a model instance.

    Args:
        instance: The model instance
        created: Whether this is a new instance

    Returns:
        Dictionary of changes
    """
    if created or not instance.pk:
        # New instance - all fields are "new"
        changes = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            if value is not None:
                changes[field.name] = {"old": None, "new": str(value)}
        return changes

    # Existing instance - compare with database
    try:
        old_instance = instance.__class__.objects.get(pk=instance.pk)
        changes = {}

        for field in instance._meta.fields:
            old_value = getattr(old_instance, field.name)
            new_value = getattr(instance, field.name)

            # Skip unchanged fields
            if old_value == new_value:
                continue

            # Handle special field types
            if hasattr(old_value, "isoformat"):  # DateTime fields
                old_value = old_value.isoformat() if old_value else None
                new_value = new_value.isoformat() if new_value else None
            else:
                old_value = str(old_value) if old_value is not None else None
                new_value = str(new_value) if new_value is not None else None

            if old_value != new_value:
                changes[field.name] = {"old": old_value, "new": new_value}

        return changes

    except instance.__class__.DoesNotExist:
        # Instance doesn't exist yet (shouldn't happen in pre_save)
        return {}


def determine_category(model: Model) -> str:
    """
    Determine the audit category based on the model type.

    Args:
        model: The model instance

    Returns:
        The audit category
    """
    model_name = model.__class__.__name__

    category_map = {
        "Person": AuditLog.CATEGORY_VOTER_DATA,
        "VoterRecord": AuditLog.CATEGORY_VOTER_DATA,
        "ContactAttempt": AuditLog.CATEGORY_CONTACT,
        "User": AuditLog.CATEGORY_AUTH,
    }

    return category_map.get(model_name, AuditLog.CATEGORY_SYSTEM)


# Model change signals
@receiver(pre_save)
def audit_model_pre_save(sender, instance, **kwargs):
    """
    Capture the state of a model before saving for change tracking.

    Args:
        sender: The model class
        instance: The model instance being saved
        **kwargs: Additional signal arguments
    """
    # Only audit specified models
    if sender not in AUDITED_MODELS:
        return

    # Store the changes on the instance for use in post_save
    instance._audit_changes = get_model_changes(instance, created=not instance.pk)
    instance._audit_is_new = not bool(instance.pk)


@receiver(post_save)
def audit_model_post_save(sender, instance, created, **kwargs):
    """
    Create audit log entry after a model is saved.

    Args:
        sender: The model class
        instance: The model instance that was saved
        created: Whether this was a new instance
        **kwargs: Additional signal arguments
    """
    # Only audit specified models
    if sender not in AUDITED_MODELS:
        return

    try:
        # Get changes from pre_save
        changes = getattr(instance, "_audit_changes", {})
        # Use the created parameter from the signal, not pre-computed value
        is_new = created

        # Skip if no changes (shouldn't happen, but be safe)
        if not is_new and not changes:
            return

        # Determine action
        action = AuditLog.ACTION_CREATE if is_new else AuditLog.ACTION_UPDATE

        # Get the current user (if available)
        user = None
        if hasattr(instance, "created_by") and is_new and instance.created_by:
            user = instance.created_by
        elif hasattr(instance, "updated_by") and instance.updated_by:
            user = instance.updated_by
        else:
            user = get_current_user()

        # Build message
        if is_new:
            message = f"Created {instance.__class__.__name__}: {str(instance)}"
        else:
            message = f"Updated {instance.__class__.__name__}: {str(instance)}"
            if changes:
                changed_fields = ", ".join(changes.keys())
                message += f" (fields: {changed_fields})"

        # Create audit log
        AuditLog.log_action(
            action=action,
            user=user,
            obj=instance,
            changes=changes,
            message=message,
            category=determine_category(instance),
            severity=AuditLog.SEVERITY_INFO,
        )

        # Clean up temporary attributes
        if hasattr(instance, "_audit_changes"):
            delattr(instance, "_audit_changes")
        if hasattr(instance, "_audit_is_new"):
            delattr(instance, "_audit_is_new")

    except Exception as e:
        logger.error(
            f"Error creating audit log for {sender.__name__}: {e}", exc_info=True
        )


@receiver(pre_delete)
def audit_model_pre_delete(sender, instance, **kwargs):
    """
    Create audit log entry before a model is deleted.

    Args:
        sender: The model class
        instance: The model instance being deleted
        **kwargs: Additional signal arguments
    """
    # Only audit specified models
    if sender not in AUDITED_MODELS:
        return

    try:
        # Check if this is a soft delete
        is_soft_delete = hasattr(instance, "is_active") and hasattr(
            instance, "deleted_at"
        )
        action = (
            AuditLog.ACTION_SOFT_DELETE if is_soft_delete else AuditLog.ACTION_DELETE
        )

        # Get the current user
        user = None
        if hasattr(instance, "deleted_by"):
            user = instance.deleted_by
        else:
            user = get_current_user()

        # Create a snapshot of the deleted object
        old_values = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            if hasattr(value, "isoformat"):
                value = value.isoformat() if value else None
            else:
                value = str(value) if value is not None else None
            old_values[field.name] = value

        # Build message
        action_text = "Soft deleted" if is_soft_delete else "Deleted"
        message = f"{action_text} {instance.__class__.__name__}: {str(instance)}"

        # Create audit log
        AuditLog.log_action(
            action=action,
            user=user,
            obj=instance,
            changes=old_values,
            message=message,
            category=determine_category(instance),
            severity=(
                AuditLog.SEVERITY_WARNING
                if not is_soft_delete
                else AuditLog.SEVERITY_INFO
            ),
        )

    except Exception as e:
        logger.error(
            f"Error creating delete audit log for {sender.__name__}: {e}",
            exc_info=True,
        )


# Authentication signals
@receiver(user_logged_in)
def audit_user_login(sender, request, user, **kwargs):
    """
    Create audit log entry when a user logs in.

    Args:
        sender: The sender of the signal
        request: The HTTP request
        user: The user who logged in
        **kwargs: Additional signal arguments
    """
    try:
        context = get_request_audit_context(request) if request else {}

        AuditLog.log_action(
            action=AuditLog.ACTION_LOGIN,
            user=user,
            message=f"User {user} logged in",
            category=AuditLog.CATEGORY_AUTH,
            severity=AuditLog.SEVERITY_INFO,
            ip_address=context.get("ip_address"),
            user_agent=context.get("user_agent"),
            metadata={
                "username": user.username,
                "email": user.email,
            },
        )
    except Exception as e:
        logger.error(f"Error logging user login: {e}", exc_info=True)


@receiver(user_logged_out)
def audit_user_logout(sender, request, user, **kwargs):
    """
    Create audit log entry when a user logs out.

    Args:
        sender: The sender of the signal
        request: The HTTP request
        user: The user who logged out
        **kwargs: Additional signal arguments
    """
    try:
        if not user:
            return

        context = get_request_audit_context(request) if request else {}

        AuditLog.log_action(
            action=AuditLog.ACTION_LOGOUT,
            user=user,
            message=f"User {user} logged out",
            category=AuditLog.CATEGORY_AUTH,
            severity=AuditLog.SEVERITY_INFO,
            ip_address=context.get("ip_address"),
            user_agent=context.get("user_agent"),
        )
    except Exception as e:
        logger.error(f"Error logging user logout: {e}", exc_info=True)


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request, **kwargs):
    """
    Create audit log entry when a login attempt fails.

    Args:
        sender: The sender of the signal
        credentials: The credentials that were attempted
        request: The HTTP request
        **kwargs: Additional signal arguments
    """
    try:
        context = get_request_audit_context(request) if request else {}
        username = credentials.get("username", "unknown")

        AuditLog.log_action(
            action=AuditLog.ACTION_LOGIN_FAILED,
            user=None,
            message=f"Failed login attempt for username: {username}",
            category=AuditLog.CATEGORY_SECURITY,
            severity=AuditLog.SEVERITY_WARNING,
            ip_address=context.get("ip_address"),
            user_agent=context.get("user_agent"),
            metadata={
                "username_attempted": username,
            },
        )

        # Use security monitoring to check for excessive failed login attempts
        if context.get("ip_address"):
            from civicpulse.utils.security_monitor import check_failed_login_attempts

            security_check = check_failed_login_attempts(
                ip_address=context["ip_address"], username=username
            )

            if security_check.get("alert_triggered"):
                logger.warning(
                    f"Security alert triggered for IP {context['ip_address']}: "
                    f"{security_check.get('failure_count')} failed login attempts"
                )
    except Exception as e:
        logger.error(f"Error logging failed login: {e}", exc_info=True)


# Custom signals for import/export operations
def log_data_export(
    user: User,
    export_type: str,
    record_count: int,
    filters: dict = None,
    **kwargs,
):
    """
    Log a data export operation and check for unusual export activity.

    Args:
        user: The user performing the export
        export_type: Type of data being exported
        record_count: Number of records exported
        filters: Any filters applied to the export
        **kwargs: Additional metadata
    """
    try:
        metadata = {
            "export_type": export_type,
            "record_count": record_count,
        }
        if filters:
            metadata["filters"] = filters
        metadata.update(kwargs)

        # Log the export operation
        AuditLog.log_action(
            action=AuditLog.ACTION_EXPORT,
            user=user,
            message=f"Exported {record_count} {export_type} records",
            category=AuditLog.CATEGORY_VOTER_DATA,
            severity=AuditLog.SEVERITY_WARNING,  # Exports are sensitive
            metadata=metadata,
        )

        # Check for unusual export activity patterns
        # This creates critical audit logs and sends email alerts if needed
        from civicpulse.utils.security_monitor import detect_unusual_export_activity

        security_check = detect_unusual_export_activity(user=user)

        if security_check.get("alert_triggered"):
            logger.warning(
                f"Security alert triggered for user {user.username}: "
                f"{security_check.get('export_count')} export operations detected"
            )

    except Exception as e:
        logger.error(f"Error logging data export: {e}", exc_info=True)


def log_data_import(
    user: User,
    import_type: str,
    record_count: int,
    filename: str = None,
    **kwargs,
):
    """
    Log a data import operation.

    Args:
        user: The user performing the import
        import_type: Type of data being imported
        record_count: Number of records imported
        filename: Name of the imported file
        **kwargs: Additional metadata
    """
    try:
        metadata = {
            "import_type": import_type,
            "record_count": record_count,
        }
        if filename:
            metadata["filename"] = filename
        metadata.update(kwargs)

        AuditLog.log_action(
            action=AuditLog.ACTION_IMPORT,
            user=user,
            message=f"Imported {record_count} {import_type} records",
            category=AuditLog.CATEGORY_VOTER_DATA,
            severity=AuditLog.SEVERITY_WARNING,  # Imports are sensitive
            metadata=metadata,
        )
    except Exception as e:
        logger.error(f"Error logging data import: {e}", exc_info=True)
