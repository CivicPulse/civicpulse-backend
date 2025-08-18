"""
Basic functionality tests for the Django project.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


class TestBasicFunctionality:
    """Test basic Django functionality works."""

    def test_admin_site_loads(self, client: Client):
        """Test that admin site loads correctly."""
        response = client.get("/admin/")
        # Should redirect to login page
        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_admin_login_page_loads(self, client: Client):
        """Test that admin login page loads."""
        response = client.get("/admin/login/")
        assert response.status_code == 200
        assert b"Django administration" in response.content

    @pytest.mark.django_db
    def test_admin_login_with_superuser(self, admin_user, client: Client):
        """Test admin login with superuser credentials."""
        client.login(username=admin_user.username, password="testpass123")
        response = client.get("/admin/")
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_create_user(self, db):
        """Test user creation works."""
        user = User.objects.create_user(
            username="newuser", email="newuser@test.com", password="testpass123"
        )
        assert user.username == "newuser"
        assert user.email == "newuser@test.com"
        assert user.check_password("testpass123")
        assert not user.is_staff
        assert not user.is_superuser

    @pytest.mark.django_db
    def test_create_superuser(self, db):
        """Test superuser creation works."""
        superuser = User.objects.create_superuser(
            username="superuser", email="super@test.com", password="testpass123"
        )
        assert superuser.username == "superuser"
        assert superuser.email == "super@test.com"
        assert superuser.is_staff
        assert superuser.is_superuser

    def test_debug_toolbar_configuration(self, settings):
        """Test that debug toolbar is properly configured for development."""
        if "debug_toolbar" in settings.INSTALLED_APPS:
            assert (
                "debug_toolbar.middleware.DebugToolbarMiddleware" in settings.MIDDLEWARE
            )
        # Test passes if no errors are raised during setup


class TestStaticAndMediaFiles:
    """Test static and media file handling."""

    def test_static_files_serve_in_debug(self, settings, client: Client):
        """Test static files are served correctly in DEBUG mode."""
        settings.DEBUG = True
        # In a real test, you'd check if static files are served correctly
        pass

    def test_media_files_configuration(self, settings):
        """Test media files configuration."""
        assert hasattr(settings, "MEDIA_URL")
        assert hasattr(settings, "MEDIA_ROOT")


class TestDatabase:
    """Test database functionality."""

    @pytest.mark.django_db
    def test_database_connection(self, db):
        """Test database connection works."""
        # Simply accessing the database should work
        user_count = User.objects.count()
        assert isinstance(user_count, int)

    @pytest.mark.django_db
    def test_migrations_are_applied(self, db):
        """Test that migrations are properly applied."""
        # Check that core Django tables exist
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='auth_user';"
            )
            result = cursor.fetchone()
            assert result is not None
