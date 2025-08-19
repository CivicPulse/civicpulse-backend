"""
Development settings for cpback project.
"""

import sys

import environ

from .base import *

env = environ.Env()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = True

# Development-specific allowed hosts
ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "0.0.0.0"]

# Add Django Debug Toolbar in development (not in testing)
if "test" not in sys.argv:
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
if "test" not in sys.argv:
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    INTERNAL_IPS: list[str] = ["127.0.0.1", "localhost"]

# Debug Toolbar configuration
IS_RUNNING_TESTS = "test" in sys.argv

DEBUG_TOOLBAR_CONFIG: dict = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
    "SHOW_TEMPLATE_CONTEXT": True,
    "IS_RUNNING_TESTS": False,  # Bypass the test check
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
