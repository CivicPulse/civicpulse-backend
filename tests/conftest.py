"""
Pytest configuration and fixtures for the CivicPulse backend tests.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

User = get_user_model()


@pytest.fixture(scope="session")
def django_db_setup():
    """Setup test database."""
    # pytest-django handles database setup automatically
    pass


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def admin_user(db):
    """Create an admin user for testing."""
    # Ensure migrations are applied (only needed once per database)
    from django.core.management import call_command
    try:
        # Try to access User model first
        User.objects.count()
    except Exception:
        # If tables don't exist, run migrations
        call_command('migrate', verbosity=0, interactive=False)

    return User.objects.create_superuser(
        username="admin", email="admin@test.com", password="testpass123"
    )


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def regular_user(db):
    """Create a regular user for testing."""
    return User.objects.create_user(
        username="testuser", email="test@test.com", password="testpass123"
    )


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Enable database access for all tests.
    This fixture ensures that all tests have access to the database.
    """
    pass


@pytest.fixture
def test_settings():
    """Override settings for tests."""
    with override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        },
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        MEDIA_ROOT="/tmp/test_media",
        STATIC_ROOT="/tmp/test_static",
    ):
        yield
