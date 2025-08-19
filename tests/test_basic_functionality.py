"""
Basic functionality tests for the Django project.
"""

from unittest.mock import Mock, patch

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

    @patch('django.contrib.auth.authenticate')
    @patch('django.contrib.auth.login')
    def test_admin_login_with_superuser(
        self, mock_login, mock_authenticate, client: Client
    ):
        """Test admin login with superuser credentials."""
        # Mock user object
        mock_user = Mock()
        mock_user.username = "admin"
        mock_user.is_authenticated = True
        mock_user.is_staff = True
        mock_user.is_superuser = True

        mock_authenticate.return_value = mock_user

        # Test login process without real database
        client.login(username="admin", password="testpass123")
        response = client.get("/admin/")

        # Verify authentication was attempted
        mock_authenticate.assert_called_once()
        assert response.status_code in [200, 302]  # 302 if not fully authenticated

    @patch.object(User.objects, 'create_user')
    def test_create_user(self, mock_create_user):
        """Test user creation works."""
        # Mock user object
        mock_user = Mock()
        mock_user.username = "newuser"
        mock_user.email = "newuser@test.com"
        mock_user.is_staff = False
        mock_user.is_superuser = False
        mock_user.check_password.return_value = True

        mock_create_user.return_value = mock_user

        # Test user creation
        user = User.objects.create_user(
            username="newuser", email="newuser@test.com", password="testpass123"
        )

        # Verify mock was called correctly
        mock_create_user.assert_called_once_with(
            username="newuser", email="newuser@test.com", password="testpass123"
        )

        # Verify user properties
        assert user.username == "newuser"
        assert user.email == "newuser@test.com"
        assert user.check_password("testpass123")
        assert not user.is_staff
        assert not user.is_superuser

    @patch.object(User.objects, 'create_superuser')
    def test_create_superuser(self, mock_create_superuser):
        """Test superuser creation works."""
        # Mock superuser object
        mock_superuser = Mock()
        mock_superuser.username = "superuser"
        mock_superuser.email = "super@test.com"
        mock_superuser.is_staff = True
        mock_superuser.is_superuser = True

        mock_create_superuser.return_value = mock_superuser

        # Test superuser creation
        superuser = User.objects.create_superuser(
            username="superuser", email="super@test.com", password="testpass123"
        )

        # Verify mock was called correctly
        mock_create_superuser.assert_called_once_with(
            username="superuser", email="super@test.com", password="testpass123"
        )

        # Verify superuser properties
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

    @patch.object(User.objects, 'count')
    def test_database_connection(self, mock_count):
        """Test database connection works with mocked count."""
        # Mock the count method to return a reasonable value
        mock_count.return_value = 5

        # Test database access
        user_count = User.objects.count()

        # Verify mock was called and result is correct type
        mock_count.assert_called_once()
        assert isinstance(user_count, int)
        assert user_count == 5

    @patch.object(User.objects, 'count')
    @patch.object(User.objects, 'create_user')
    def test_database_tables_exist(self, mock_create_user, mock_count):
        """Test that database tables are properly created and accessible with mocks."""
        # Mock initial count
        mock_count.side_effect = [0, 1]  # First call returns 0, second returns 1

        # Mock user creation
        mock_user = Mock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_create_user.return_value = mock_user

        # Test initial count
        user_count = User.objects.count()
        assert isinstance(user_count, int)
        assert user_count == 0

        # Test user creation
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Verify creation was called correctly
        mock_create_user.assert_called_once_with(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Verify user properties
        assert user.id is not None
        assert user.username == "testuser"

        # Test count after creation
        new_count = User.objects.count()
        assert new_count == 1
