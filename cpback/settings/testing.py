"""
Testing settings for cpback project.
Isolated test configuration that doesn't depend on external environment variables.
"""

import os

# Set required environment variables for testing if not already set
# This must be done BEFORE importing base settings
if not os.environ.get("SECRET_KEY"):
    # Generate a secure secret key for testing to avoid validation errors
    from django.core.management.utils import get_random_secret_key

    os.environ["SECRET_KEY"] = get_random_secret_key()

from .base import *  # noqa: F403,F401

# Override settings for testing
DEBUG: bool = False

# Explicitly remove debug toolbar and development-only apps from testing
INSTALLED_APPS = [  # noqa: F405
    app
    for app in INSTALLED_APPS  # noqa: F405
    if app not in ["debug_toolbar", "django_extensions"]
]

# Clean middleware list - remove debug toolbar completely
MIDDLEWARE = [  # noqa: F405
    middleware
    for middleware in MIDDLEWARE  # noqa: F405
    if middleware != "debug_toolbar.middleware.DebugToolbarMiddleware"
]

# Use in-memory database for tests, unless DATABASE_URL is provided (e.g., for CI)
if "DATABASE_URL" in os.environ:
    # Use the database URL from environment (typically PostgreSQL in CI)
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"])}
else:
    # Use in-memory SQLite for local testing
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

# Use local memory cache for tests
CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# Use in-memory email backend for tests (doesn't print to console)
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"  # noqa: F405

# Use fastest password hashers for testing
PASSWORD_HASHERS: list[str] = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Minimal logging for tests - reduce noise
LOGGING = {  # noqa: F405
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
        "console": {
            "level": "ERROR",
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["null"],
        "level": "ERROR",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "civicpulse": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# Security settings can be relaxed for testing
SECURE_SSL_REDIRECT = False  # noqa: F405
SESSION_COOKIE_SECURE = False  # noqa: F405
CSRF_COOKIE_SECURE = False  # noqa: F405

# Disable security middleware checks that can interfere with testing
SECURE_BROWSER_XSS_FILTER = False  # noqa: F405
SECURE_CONTENT_TYPE_NOSNIFF = False  # noqa: F405

# Allow all email domains for testing
SUSPICIOUS_EMAIL_DOMAINS = []  # noqa: F405

# Override authentication backends for testing to avoid AXES issues
AUTHENTICATION_BACKENDS = [  # noqa: F405
    "django.contrib.auth.backends.ModelBackend",
]

# Disable AXES for testing
AXES_ENABLED = False  # noqa: F405

# Disable rate limiting for testing
RATELIMIT_ENABLE = False  # noqa: F405

# Test-specific settings
TEST_RUNNER = "django.test.runner.DiscoverRunner"  # noqa: F405

# Set ALLOWED_HOSTS for testing
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]  # noqa: F405

# Disable migrations for faster testing (optional - can be enabled if needed)
# class DisableMigrations:
#     def __contains__(self, item):
#         return True
#
#     def __getitem__(self, item):
#         return None
#
# MIGRATION_MODULES = DisableMigrations()  # noqa: F405
