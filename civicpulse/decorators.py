"""
Role-based access control decorators and mixins for the CivicPulse application.

Provides decorators and class-based view mixins for implementing fine-grained
permission control based on user roles and authentication status.
"""

import functools
import logging
from collections.abc import Callable

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

User = get_user_model()
logger = logging.getLogger(__name__)


def role_required(*allowed_roles: str):
    """
    Decorator that requires the user to have one of the specified roles.

    Args:
        *allowed_roles: Variable number of role names that are allowed

    Returns:
        Decorated view function that checks user role

    Raises:
        PermissionDenied: If user doesn't have required role

    Example:
        @role_required('admin', 'organizer')
        def admin_only_view(request):
            return render(request, 'admin/dashboard.html')
    """

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        @login_required
        def wrapped_view(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            user = request.user

            # Check if user has required role
            if user.role not in allowed_roles:
                logger.warning(
                    f"Access denied: User {user.username} with role '{user.role}' "
                    f"attempted to access view requiring roles: {allowed_roles}"
                )
                raise PermissionDenied(
                    f"Access denied. Required role: {' or '.join(allowed_roles)}"
                )

            logger.debug(
                f"Access granted: User {user.username} with role '{user.role}' "
                f"accessing view requiring roles: {allowed_roles}"
            )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


def admin_required(view_func: Callable) -> Callable:
    """
    Decorator that requires the user to have admin role.

    Args:
        view_func: The view function to decorate

    Returns:
        Decorated view function that checks for admin role
    """
    return role_required("admin")(view_func)


def organizer_required(view_func: Callable) -> Callable:
    """
    Decorator that requires the user to have organizer or admin role.

    Args:
        view_func: The view function to decorate

    Returns:
        Decorated view function that checks for organizer or admin role
    """
    return role_required("admin", "organizer")(view_func)


def staff_required(view_func: Callable) -> Callable:
    """
    Decorator that requires the user to have admin, organizer, or volunteer role.

    Args:
        view_func: The view function to decorate

    Returns:
        Decorated view function that checks for staff roles
    """
    return role_required("admin", "organizer", "volunteer")(view_func)


def verified_required(view_func: Callable) -> Callable:
    """
    Decorator that requires the user to have a verified email address.

    Args:
        view_func: The view function to decorate

    Returns:
        Decorated view function that checks for email verification
    """

    @functools.wraps(view_func)
    @login_required
    def wrapped_view(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        user = request.user

        # Check if user is verified
        if hasattr(user, "is_verified") and not user.is_verified:
            logger.warning(
                f"Access denied: Unverified user {user.username} "
                f"attempted to access verified-only view"
            )
            return redirect("registration_complete")

        return view_func(request, *args, **kwargs)

    return wrapped_view


def organization_member_required(view_func: Callable) -> Callable:
    """
    Decorator that requires the user to belong to an organization.

    Args:
        view_func: The view function to decorate

    Returns:
        Decorated view function that checks for organization membership
    """

    @functools.wraps(view_func)
    @login_required
    def wrapped_view(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        user = request.user

        # Check if user belongs to an organization
        if not user.organization:
            logger.warning(
                f"Access denied: User {user.username} without organization "
                f"attempted to access organization-only view"
            )
            raise PermissionDenied("Access denied. You must belong to an organization.")

        return view_func(request, *args, **kwargs)

    return wrapped_view


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin for class-based views that requires specific user roles.

    Attributes:
        allowed_roles: List or tuple of role names that are allowed
        permission_denied_message: Custom message for permission denied errors

    Example:
        class AdminOnlyView(RoleRequiredMixin, TemplateView):
            allowed_roles = ['admin']
            template_name = 'admin/dashboard.html'
    """

    allowed_roles: list | tuple = []
    permission_denied_message: str = "You don't have permission to access this page."

    def test_func(self) -> bool:
        """Test if the user has the required role."""
        if not self.allowed_roles:
            logger.error(
                f"RoleRequiredMixin used in {self.__class__.__name__} "
                f"but no allowed_roles specified"
            )
            return False

        user = self.request.user
        has_permission = user.role in self.allowed_roles

        if not has_permission:
            logger.warning(
                f"Access denied: User {user.username} with role '{user.role}' "
                f"attempted to access {self.__class__.__name__} "
                f"requiring roles: {self.allowed_roles}"
            )
        else:
            logger.debug(
                f"Access granted: User {user.username} with role '{user.role}' "
                f"accessing {self.__class__.__name__}"
            )

        return has_permission

    def get_permission_denied_message(self) -> str:
        """Get the permission denied message."""
        if self.allowed_roles:
            return f"Access denied. Required role: {' or '.join(self.allowed_roles)}"
        return self.permission_denied_message


class AdminRequiredMixin(RoleRequiredMixin):
    """Mixin that requires admin role."""

    allowed_roles = ["admin"]


class OrganizerRequiredMixin(RoleRequiredMixin):
    """Mixin that requires organizer or admin role."""

    allowed_roles = ["admin", "organizer"]


class StaffRequiredMixin(RoleRequiredMixin):
    """Mixin that requires admin, organizer, or volunteer role."""

    allowed_roles = ["admin", "organizer", "volunteer"]


class VerifiedRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin that requires the user to have a verified email address.

    Redirects unverified users to the registration complete page.
    """

    def test_func(self) -> bool:
        """Test if the user is verified."""
        user = self.request.user
        is_verified = not hasattr(user, "is_verified") or user.is_verified

        if not is_verified:
            logger.warning(
                f"Access denied: Unverified user {user.username} "
                f"attempted to access {self.__class__.__name__}"
            )

        return is_verified

    def handle_no_permission(self) -> HttpResponse:
        """Redirect unverified users to registration complete page."""
        if self.request.user.is_authenticated:
            return redirect("registration_complete")
        return super().handle_no_permission()


class OrganizationMemberMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin that requires the user to belong to an organization.
    """

    def test_func(self) -> bool:
        """Test if the user belongs to an organization."""
        user = self.request.user
        has_organization = bool(user.organization)

        if not has_organization:
            logger.warning(
                f"Access denied: User {user.username} without organization "
                f"attempted to access {self.__class__.__name__}"
            )

        return has_organization

    def get_permission_denied_message(self) -> str:
        """Get the permission denied message."""
        return "You must belong to an organization to access this page."


class SameUserOrAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin that allows access if the user is the same user being accessed
    or if the user is an admin.

    Expects a 'username' URL parameter to identify the target user.
    """

    def test_func(self) -> bool:
        """Test if user can access the profile."""
        current_user = self.request.user
        target_username = self.kwargs.get("username")

        # Allow access if user is admin or accessing their own profile
        is_admin = current_user.role == "admin"
        is_same_user = current_user.username == target_username

        has_permission = is_admin or is_same_user

        if not has_permission:
            logger.warning(
                f"Access denied: User {current_user.username} "
                f"attempted to access profile of {target_username}"
            )

        return has_permission

    def get_permission_denied_message(self) -> str:
        """Get the permission denied message."""
        return "You can only access your own profile."


# Utility functions for template usage


def user_has_role(user, *roles: str) -> bool:
    """
    Check if a user has one of the specified roles.

    Args:
        user: User instance
        *roles: Variable number of role names to check

    Returns:
        True if user has one of the specified roles

    Example:
        {% if user|user_has_role:"admin,organizer" %}
            <p>Admin or organizer content</p>
        {% endif %}
    """
    if not user or not user.is_authenticated:
        return False

    return user.role in roles


def user_is_admin(user) -> bool:
    """Check if user is an admin."""
    return user_has_role(user, "admin")


def user_is_organizer_or_admin(user) -> bool:
    """Check if user is an organizer or admin."""
    return user_has_role(user, "admin", "organizer")


def user_is_staff(user) -> bool:
    """Check if user is staff (admin, organizer, or volunteer)."""
    return user_has_role(user, "admin", "organizer", "volunteer")


def user_can_edit_profile(user, target_user) -> bool:
    """
    Check if a user can edit another user's profile.

    Args:
        user: Current user
        target_user: User whose profile is being accessed

    Returns:
        True if user can edit the target user's profile
    """
    if not user or not user.is_authenticated:
        return False

    # Users can edit their own profile, admins can edit any profile
    return user == target_user or user.role == "admin"
