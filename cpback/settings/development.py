"""
Development settings for cpback project.
"""

import os
import sys

import environ

from .base import *

env = environ.Env()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Development-specific allowed hosts
ALLOWED_HOSTS.extend(["localhost", "127.0.0.1", "0.0.0.0"])

# Add Django Debug Toolbar in development (not in testing)
# Check for testing conditions to prevent debug toolbar issues
IS_TESTING = (
    "test" in sys.argv
    or "pytest" in sys.modules
    or os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("testing")
)

if not IS_TESTING:
    THIRD_PARTY_APPS.extend(
        [
            "debug_toolbar",
            "django_extensions",
        ]
    )

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Database
# Uses DATABASE_URL from .env file (defaults to SQLite for development)
# To use PostgreSQL, update DATABASE_URL in .env file

# Email backend for development
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)

# Django Debug Toolbar configuration (not in testing)
if not IS_TESTING:
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    INTERNAL_IPS: list[str] = ["127.0.0.1", "localhost"]

    # Debug Toolbar configuration
    DEBUG_TOOLBAR_CONFIG: dict = {
        "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG and not IS_TESTING,
        "SHOW_TEMPLATE_CONTEXT": True,
        "IS_RUNNING_TESTS": IS_TESTING,
    }

# Development-specific logging
LOGGING["handlers"]["console"]["level"] = "DEBUG"
LOGGING["loggers"]["civicpulse"]["level"] = "DEBUG"

# Disable HTTPS redirects in development
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# CORS settings for development (if django-cors-headers is used)
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
