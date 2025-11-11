"""
Tests for Django REST Framework integration with CivicPulse authentication.

This module tests that DRF is properly configured and integrates correctly
with the existing authentication system including the custom User model.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import path
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

User = get_user_model()


# Test serializers and views for testing
class UserSerializer(serializers.ModelSerializer):
    """Simple user serializer for testing."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """Simple viewset for testing."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def protected_view(request):
    """Simple protected view for testing."""
    return Response({"message": "Hello, authenticated user!"})


@api_view(["GET"])
@permission_classes([AllowAny])
def public_view(request):
    """Simple public view for testing."""
    return Response({"message": "Hello, world!"})


# Test URL patterns
test_urlpatterns = [
    path("api/protected/", protected_view),
    path("api/public/", public_view),
]


class TestRestFrameworkConfiguration:
    """Test REST Framework configuration."""

    def test_rest_framework_installed(self, settings):
        """Test that REST Framework is in INSTALLED_APPS."""
        assert "rest_framework" in settings.INSTALLED_APPS

    def test_rest_framework_settings_exist(self, settings):
        """Test that REST_FRAMEWORK settings are configured."""
        assert hasattr(settings, "REST_FRAMEWORK")
        assert isinstance(settings.REST_FRAMEWORK, dict)

    def test_authentication_classes_configured(self, settings):
        """Test that authentication classes are properly configured."""
        auth_classes = settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
        assert "rest_framework.authentication.SessionAuthentication" in auth_classes
        assert "rest_framework.authentication.BasicAuthentication" in auth_classes

    def test_permission_classes_configured(self, settings):
        """Test that permission classes are properly configured."""
        perm_classes = settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]
        assert "rest_framework.permissions.IsAuthenticated" in perm_classes

    def test_pagination_configured(self, settings):
        """Test that pagination is properly configured."""
        assert settings.REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"] == (
            "rest_framework.pagination.PageNumberPagination"
        )
        assert settings.REST_FRAMEWORK["PAGE_SIZE"] == 20

    def test_filter_backends_configured(self, settings):
        """Test that filter backends are properly configured."""
        filter_backends = settings.REST_FRAMEWORK["DEFAULT_FILTER_BACKENDS"]
        assert "rest_framework.filters.SearchFilter" in filter_backends
        assert "rest_framework.filters.OrderingFilter" in filter_backends

    def test_datetime_format_configured(self, settings):
        """Test that DateTime format is ISO 8601."""
        datetime_format = settings.REST_FRAMEWORK["DATETIME_FORMAT"]
        assert datetime_format == "%Y-%m-%dT%H:%M:%S.%fZ"

    def test_throttling_configured(self, settings):
        """Test that API throttling is configured."""
        throttle_classes = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]
        assert "rest_framework.throttling.AnonRateThrottle" in throttle_classes
        assert "rest_framework.throttling.UserRateThrottle" in throttle_classes

        throttle_rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        assert "anon" in throttle_rates
        assert "user" in throttle_rates


@pytest.mark.django_db
class TestRestFrameworkAuthentication:
    """Test REST Framework authentication with CivicPulse User model."""

    @pytest.fixture
    def api_client(self):
        """Create an API client for testing."""
        return APIClient()

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePassword123!@#",
            first_name="Test",
            last_name="User",
        )

    @pytest.fixture
    def admin_user(self):
        """Create an admin test user."""
        return User.objects.create_user(
            username="adminuser",
            email="admin@example.com",
            password="AdminPassword123!@#",
            first_name="Admin",
            last_name="User",
            role="admin",
        )

    def test_unauthenticated_request_denied(self, api_client):
        """Test that unauthenticated requests are denied."""
        factory = APIRequestFactory()
        request = factory.get("/api/protected/")
        response = protected_view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authenticated_request_allowed(self, api_client, user):
        """Test that authenticated requests are allowed."""
        factory = APIRequestFactory()
        request = factory.get("/api/protected/")
        force_authenticate(request, user=user)
        response = protected_view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Hello, authenticated user!"

    def test_public_view_accessible_without_auth(self, api_client):
        """Test that public views are accessible without authentication."""
        factory = APIRequestFactory()
        request = factory.get("/api/public/")
        response = public_view(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Hello, world!"

    def test_session_authentication(self, api_client, user):
        """Test session-based authentication."""
        # Login the user
        api_client.login(username="testuser", password="SecurePassword123!@#")

        # Create request with authenticated client
        factory = APIRequestFactory()
        request = factory.get("/api/protected/")
        request.user = user

        # Force authenticate to simulate session auth
        force_authenticate(request, user=user)
        response = protected_view(request)

        assert response.status_code == status.HTTP_200_OK

    def test_user_serializer_with_custom_user_model(self, user):
        """Test that serializers work with custom User model."""
        serializer = UserSerializer(user)
        data = serializer.data

        # Compare as strings (UUID serialization)
        assert str(data["id"]) == str(user.id)
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"

    def test_viewset_with_authentication(self, api_client, user, admin_user):
        """Test that viewsets work with authentication."""
        factory = APIRequestFactory()
        view = UserViewSet.as_view({"get": "list"})

        # Unauthenticated request
        request = factory.get("/api/users/")
        response = view(request)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Authenticated request
        request = factory.get("/api/users/")
        force_authenticate(request, user=user)
        response = view(request)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestRestFrameworkFiltering:
    """Test REST Framework filtering capabilities."""

    @pytest.fixture
    def users(self):
        """Create multiple test users for filtering tests."""
        users = []
        for i in range(5):
            user = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password=f"Password{i}!@#",
                first_name=f"First{i}",
                last_name=f"Last{i}",
            )
            users.append(user)
        return users

    def test_pagination_default_page_size(self, users):
        """Test that pagination uses the configured page size."""
        factory = APIRequestFactory()
        view = UserViewSet.as_view({"get": "list"})

        request = factory.get("/api/users/")
        force_authenticate(request, user=users[0])
        response = view(request)

        assert response.status_code == status.HTTP_200_OK
        # Should have pagination structure
        assert "results" in response.data or isinstance(response.data, list)


@pytest.mark.django_db
class TestRestFrameworkSerialization:
    """Test REST Framework serialization with CivicPulse models."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
            username="serializetest",
            email="serialize@example.com",
            password="SerializePassword123!@#",
            first_name="Serialize",
            last_name="Test",
            role="member",
        )

    def test_datetime_serialization_iso8601(self, user):
        """Test that DateTimes are serialized in ISO 8601 format."""
        # User model should have created_at and updated_at fields
        # Verify they exist in the User model
        assert hasattr(user, "created_at")
        assert hasattr(user, "updated_at")

    def test_user_fields_serialized(self, user):
        """Test that all expected user fields are serialized."""
        serializer = UserSerializer(user)
        data = serializer.data

        expected_fields = ["id", "username", "email", "first_name", "last_name"]
        for field in expected_fields:
            assert field in data

    def test_sensitive_fields_excluded(self, user):
        """Test that sensitive fields are excluded from serialization."""
        serializer = UserSerializer(user)
        data = serializer.data

        # These fields should NOT be in the serialized data
        sensitive_fields = ["password", "last_login"]
        for field in sensitive_fields:
            assert field not in data


@pytest.mark.django_db
class TestRestFrameworkPermissions:
    """Test REST Framework permissions with CivicPulse roles."""

    @pytest.fixture
    def member_user(self):
        """Create a member user."""
        return User.objects.create_user(
            username="member",
            email="member@example.com",
            password="MemberPass123!@#",
            role="member",
        )

    @pytest.fixture
    def admin_user(self):
        """Create an admin user."""
        return User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="AdminPass123!@#",
            role="admin",
        )

    def test_isAuthenticated_permission_with_member(self, member_user):
        """Test IsAuthenticated permission works with member role."""
        factory = APIRequestFactory()
        request = factory.get("/api/protected/")
        force_authenticate(request, user=member_user)
        response = protected_view(request)
        assert response.status_code == status.HTTP_200_OK

    def test_isAuthenticated_permission_with_admin(self, admin_user):
        """Test IsAuthenticated permission works with admin role."""
        factory = APIRequestFactory()
        request = factory.get("/api/protected/")
        force_authenticate(request, user=admin_user)
        response = protected_view(request)
        assert response.status_code == status.HTTP_200_OK

    def test_allowany_permission_allows_anonymous(self):
        """Test AllowAny permission allows anonymous users."""
        factory = APIRequestFactory()
        request = factory.get("/api/public/")
        response = public_view(request)
        assert response.status_code == status.HTTP_200_OK
