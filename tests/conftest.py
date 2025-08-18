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
    # Use in-memory SQLite for tests
    pass


@pytest.fixture
@pytest.mark.django_db
def admin_user(db):
    """Create an admin user for testing."""
    return User.objects.create_superuser(
        username="admin", email="admin@test.com", password="testpass123"
    )


@pytest.fixture
@pytest.mark.django_db
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
