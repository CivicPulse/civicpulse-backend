"""
Current user middleware for tracking the active user in thread-local storage.

This middleware stores the current request user in thread-local storage,
allowing signal handlers and other parts of the application to access
the current user without requiring the request to be passed around.
"""

import threading

from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

User = get_user_model()

# Thread-local storage for current request data
_thread_locals = threading.local()


class CurrentUserMiddleware(MiddlewareMixin):
    """
    Middleware that stores the current user and request in thread-local storage.

    This allows other parts of the application (like signal handlers) to access
    the current user without requiring the request to be passed around.
    """

    def process_request(self, request: HttpRequest) -> None:
        """
        Store the current request and user in thread-local storage.

        Args:
            request: The incoming HTTP request
        """
        _thread_locals.request = request
        _thread_locals.user = getattr(request, "user", None)

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """
        Clean up thread-local storage after the response is processed.

        Args:
            request: The HTTP request
            response: The HTTP response

        Returns:
            The response unchanged
        """
        # Clean up thread-local storage to prevent memory leaks
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")
        if hasattr(_thread_locals, "user"):
            delattr(_thread_locals, "user")

        return response

    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        """
        Clean up thread-local storage if an exception occurs.

        Args:
            request: The HTTP request
            exception: The exception that occurred
        """
        # Clean up thread-local storage even if an exception occurs
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")
        if hasattr(_thread_locals, "user"):
            delattr(_thread_locals, "user")


def get_current_user() -> User | None:
    """
    Get the current user from thread-local storage.

    This function can be called from anywhere in the application to get
    the user associated with the current request.

    Returns:
        The current user if available, None otherwise
    """
    user = getattr(_thread_locals, "user", None)

    # Only return authenticated users
    if user and hasattr(user, "is_authenticated") and user.is_authenticated:
        return user

    return None


def get_current_request() -> HttpRequest | None:
    """
    Get the current request from thread-local storage.

    This function can be called from anywhere in the application to get
    the request object for the current thread.

    Returns:
        The current request if available, None otherwise
    """
    return getattr(_thread_locals, "request", None)


def set_current_user(user: User | None) -> None:
    """
    Manually set the current user in thread-local storage.

    This is useful for testing or for operations that occur outside
    of a normal request cycle (like management commands).

    Args:
        user: The user to set as current
    """
    _thread_locals.user = user


def clear_current_user() -> None:
    """
    Clear the current user from thread-local storage.

    This is useful for cleanup in tests or when manually managing
    the current user context.
    """
    if hasattr(_thread_locals, "user"):
        delattr(_thread_locals, "user")
    if hasattr(_thread_locals, "request"):
        delattr(_thread_locals, "request")
