"""
Signal handlers for the civicpulse app.
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver

from civicpulse.models import PasswordHistory

User = get_user_model()


@receiver(pre_save, sender=User)
def save_password_history(sender, instance, **kwargs):
    """
    Save password to history when user's password changes.

    This signal handler tracks password changes and stores them in the
    PasswordHistory model to prevent password reuse.
    """
    # Don't save history if it's a new user (no pk yet)
    # Also check if the user actually exists in the database
    if not instance.pk or instance._state.adding:
        return

    try:
        # Get the existing user from the database
        existing_user = User.objects.get(pk=instance.pk)

        # Check if password has changed
        if existing_user.password != instance.password:
            # Save the NEW password to history (not the old one)
            # This ensures we track all passwords that have been used
            PasswordHistory.objects.create(
                user=instance, password_hash=instance.password
            )

            # Clean up old password history entries (keep only last 10)
            # This prevents the table from growing indefinitely
            old_entries = PasswordHistory.objects.filter(user=instance).order_by(
                "-created_at"
            )[10:]

            for entry in old_entries:
                entry.delete()

    except User.DoesNotExist:
        # User doesn't exist yet (shouldn't happen in pre_save)
        pass
