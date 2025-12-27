"""
CivicPulse settings configuration.

Usage in Django settings::

    CIVICPULSE = {
        "LOCK_TIMEOUT_MINUTES": 15,
        "USE_COMPRESSOR": True,
        "SITE_NAME": "My Organization",
    }

All settings are optional and have sensible defaults.
"""

from django.conf import settings

DEFAULTS = {
    # Lock timeout for concurrent user support (minutes)
    # After this time, abandoned locks are released
    "LOCK_TIMEOUT_MINUTES": 10,
    # Whether to use django-compressor for CSS compression
    # Requires django-compressor to be installed and configured
    "USE_COMPRESSOR": False,
    # Site name for branding in templates
    "SITE_NAME": "CivicPulse",
    # Whether to include the default navigation bar
    "INCLUDE_DEFAULT_NAV": True,
    # CDN URLs (can be overridden for self-hosting)
    "CDN_FLOWBITE": "https://cdn.jsdelivr.net/npm/flowbite@4.0.1/dist/flowbite.min.js",
    "CDN_HTMX": "https://unpkg.com/htmx.org@2.0.4",
}


class CivicPulseSettings:
    """
    Lazy settings object that reads from Django settings.

    Access settings via the civicpulse_settings instance::

        from civicpulse.conf import civicpulse_settings

        timeout = civicpulse_settings.LOCK_TIMEOUT_MINUTES
    """

    def __getattr__(self, name):
        if name not in DEFAULTS:
            raise AttributeError(f"Unknown CivicPulse setting: {name}")

        user_settings = getattr(settings, "CIVICPULSE", {})
        return user_settings.get(name, DEFAULTS[name])

    def __dir__(self):
        return list(DEFAULTS.keys())


civicpulse_settings = CivicPulseSettings()
