from django.apps import AppConfig


class CivicpulseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "civicpulse"

    def ready(self):
        """Import signal handlers when the app is ready."""
        import civicpulse.signals  # noqa: F401
