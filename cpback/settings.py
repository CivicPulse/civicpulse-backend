"""
Django settings dispatcher for cpback project.

This file determines which settings module to use based on the DJANGO_SETTINGS_MODULE
environment variable or defaults to development settings.
"""

import os

# Determine which settings to use
settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")

if not settings_module:
    # Default to development settings if not specified
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cpback.settings.development")

# Import the appropriate settings
if "production" in os.environ.get("DJANGO_SETTINGS_MODULE", ""):
    from .settings.production import *
elif "development" in os.environ.get("DJANGO_SETTINGS_MODULE", ""):
    from .settings.development import *
else:
    # Default fallback to development
    from .settings.development import *
