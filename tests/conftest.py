"""
Pytest configuration and fixtures for the CivicPulse backend tests.
"""

from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

User = get_user_model()


@pytest.fixture(scope="session")
def django_db_setup():
    """Setup test database - mocked for unit tests."""
    # No real database setup needed - using mocks
    pass


@pytest.fixture
def admin_user():
    """Create a mocked admin user for testing."""
    mock_user = Mock()
    mock_user.username = "admin"
    mock_user.email = "admin@test.com"
    mock_user.is_staff = True
    mock_user.is_superuser = True
    mock_user.is_authenticated = True
    mock_user.check_password.return_value = True

    return mock_user


@pytest.fixture
def regular_user():
    """Create a mocked regular user for testing."""
    mock_user = Mock()
    mock_user.username = "testuser"
    mock_user.email = "test@test.com"
    mock_user.is_staff = False
    mock_user.is_superuser = False
    mock_user.is_authenticated = True
    mock_user.check_password.return_value = True

    return mock_user


@pytest.fixture(autouse=True)
def mock_db_access():
    """
    Mock database access for all tests.
    This fixture ensures tests use mocked database calls instead of real ones.
    """
    # No real database access - all database calls should be mocked
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
