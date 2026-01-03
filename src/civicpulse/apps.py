from django.apps import AppConfig


class CivicpulseConfig(AppConfig):
    """Django app configuration for CivicPulse."""

    name = "civicpulse"
    verbose_name = "CivicPulse"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """Perform app initialization on startup."""
        # Import signals if needed in the future
        pass
