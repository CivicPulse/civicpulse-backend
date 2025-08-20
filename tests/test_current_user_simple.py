"""
Simple tests for the current user middleware functionality.
"""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from civicpulse.middleware.current_user import (
    CurrentUserMiddleware,
    clear_current_user,
    get_current_request,
    get_current_user,
    set_current_user,
)


@pytest.fixture
def middleware():
    """Create a CurrentUserMiddleware instance."""

    def get_response(request):
        return HttpResponse()

    return CurrentUserMiddleware(get_response)


@pytest.fixture
def request_factory():
    """Create a RequestFactory instance."""
    return RequestFactory()


class MockUser:
    """Mock user for testing."""

    def __init__(self, is_authenticated=True, username="testuser"):
        self.is_authenticated = is_authenticated
        self.username = username

    def __str__(self):
        return self.username


class TestCurrentUserFunctions:
    """Test the standalone functions without database dependencies."""

    def test_set_and_clear_current_user(self):
        """Test manually setting and clearing the current user."""
        # Clear any existing user
        clear_current_user()
        assert get_current_user() is None

        # Create a mock user
        user = MockUser()

        # Manually set the user
        set_current_user(user)
        assert get_current_user() == user

        # Clear manually
        clear_current_user()
        assert get_current_user() is None

    def test_get_current_user_with_unauthenticated_user(
        self, middleware, request_factory
    ):
        """Test that get_current_user returns None for unauthenticated users."""
        # Clear any existing user
        clear_current_user()

        # Create a mock user that's not authenticated
        user = MockUser(is_authenticated=False)

        # Create a request with unauthenticated user
        request = request_factory.get("/")
        request.user = user

        # Store the user
        middleware.process_request(request)

        # get_current_user should return None for unauthenticated users
        assert get_current_user() is None

    def test_process_request_stores_authenticated_user(
        self, middleware, request_factory
    ):
        """Test that process_request stores authenticated users."""
        # Clear any existing user
        clear_current_user()

        # Create a mock authenticated user
        user = MockUser(is_authenticated=True)

        # Create a request with authenticated user
        request = request_factory.get("/")
        request.user = user

        # Process the request
        middleware.process_request(request)

        # Verify the user is stored and accessible
        assert get_current_user() == user
        assert get_current_request() == request

    def test_process_response_clears_storage(self, middleware, request_factory):
        """Test that process_response clears thread-local storage."""
        # Set up a user first
        user = MockUser()
        request = request_factory.get("/")
        request.user = user
        middleware.process_request(request)

        # Verify user is stored
        assert get_current_user() == user

        # Process response
        response = HttpResponse()
        result = middleware.process_response(request, response)

        # Verify storage is cleared and response is returned
        assert get_current_user() is None
        assert get_current_request() is None
        assert result == response

    def test_process_exception_clears_storage(self, middleware, request_factory):
        """Test that process_exception clears thread-local storage."""
        # Set up a user first
        user = MockUser()
        request = request_factory.get("/")
        request.user = user
        middleware.process_request(request)

        # Verify user is stored
        assert get_current_user() == user

        # Process exception
        exception = Exception("Test exception")
        middleware.process_exception(request, exception)

        # Verify storage is cleared
        assert get_current_user() is None
        assert get_current_request() is None

    def test_no_user_in_request(self, middleware, request_factory):
        """Test handling when request has no user attribute."""
        # Clear any existing user
        clear_current_user()

        # Create a request without user attribute
        request = request_factory.get("/")
        # Don't set request.user

        # Process the request
        middleware.process_request(request)

        # Should handle gracefully
        assert get_current_user() is None
        assert get_current_request() == request
