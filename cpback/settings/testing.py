"""
Testing settings for cpback project.
"""

import os

import dj_database_url

from .development import *  # noqa: F403,F401

# Override settings for testing
DEBUG: bool = False

# Remove debug toolbar from testing
if "debug_toolbar" in INSTALLED_APPS:  # noqa: F405
    INSTALLED_APPS.remove("debug_toolbar")  # noqa: F405

if "debug_toolbar.middleware.DebugToolbarMiddleware" in MIDDLEWARE:  # noqa: F405
    MIDDLEWARE.remove("debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405

# Use in-memory database for tests, unless DATABASE_URL is provided (e.g., for CI)
if "DATABASE_URL" in os.environ:
    # Use the database URL from environment (typically PostgreSQL in CI)
    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"])}
else:
    # Use in-memory SQLite for local testing
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

# Keep migrations enabled for testing to ensure database schema is correct
# If you want to disable migrations for faster tests, uncomment below:
# class DisableMigrations:
#     def __contains__(self, item):
#         return True
#
#     def __getitem__(self, item):
#         return None
#
# MIGRATION_MODULES = DisableMigrations()  # noqa: F405

# Use local memory cache for tests
CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Use console email backend for tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"  # noqa: F405

# Password hashers for faster tests
PASSWORD_HASHERS: list[str] = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Logging for tests - minimal logging
LOGGING["handlers"]["console"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["civicpulse"]["level"] = "WARNING"  # noqa: F405

# Security settings can be relaxed for testing
SECURE_SSL_REDIRECT = False  # noqa: F405
SESSION_COOKIE_SECURE = False  # noqa: F405
CSRF_COOKIE_SECURE = False  # noqa: F405

# Allow all email domains for testing
SUSPICIOUS_EMAIL_DOMAINS = []  # noqa: F405
