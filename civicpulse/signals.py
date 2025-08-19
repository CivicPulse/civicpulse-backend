"""
Signal handlers for the civicpulse app.
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from civicpulse.models import PasswordHistory

User = get_user_model()


@receiver(pre_save, sender=User)
def track_password_changes(sender, instance, **kwargs):
    """
    Track the current password state before saving for comparison.

    This signal runs before the user is saved to capture the previous password.
    """
    if instance.pk:
        try:
            # Get the current password from database
            old_user = User.objects.get(pk=instance.pk)
            instance._old_password = old_user.password
        except User.DoesNotExist:
            instance._old_password = None
    else:
        # New user - no old password
        instance._old_password = None


@receiver(post_save, sender=User)
def save_password_history(sender, instance, created, **kwargs):
    """
    Save password to history when user is created or password changes.

    This signal handler tracks password changes and stores them in the
    PasswordHistory model to prevent password reuse.

    Args:
        sender: The model class (User)
        instance: The user instance being saved
        created: Boolean indicating if this is a new user
        **kwargs: Additional keyword arguments
    """
    password_changed = False

    if created:
        # For new users, always save the initial password
        password_changed = True
    else:
        # For existing users, check if password has changed
        old_password = getattr(instance, "_old_password", None)
        if old_password != instance.password:
            password_changed = True

    if password_changed:
        # Save the current password to history
        PasswordHistory.objects.create(user=instance, password_hash=instance.password)

        # Clean up old password history entries (keep only last 10)
        # This prevents the table from growing indefinitely
        old_entries = PasswordHistory.objects.filter(user=instance).order_by(
            "-created_at"
        )[10:]

        for entry in old_entries:
            entry.delete()
