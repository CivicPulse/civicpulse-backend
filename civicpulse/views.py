"""
Secure authentication views for the CivicPulse application.

Provides comprehensive authentication functionality including login, logout,
registration, password reset, and role-based access control with enhanced
security features.
"""

import logging
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, TemplateView

from .forms import (
    PasswordChangeForm,
    SecureLoginForm,
    SecurePasswordResetForm,
    SecureSetPasswordForm,
    SecureUserRegistrationForm,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# Rate limiting configuration
MAX_LOGIN_ATTEMPTS = getattr(settings, "MAX_LOGIN_ATTEMPTS", 5)
LOGIN_LOCKOUT_DURATION = getattr(settings, "LOGIN_LOCKOUT_DURATION", 300)  # 5 minutes


def get_client_ip(request: HttpRequest) -> str:
    """Get client IP address from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def is_rate_limited(request: HttpRequest, action: str = "login") -> bool:
    """Check if client is rate limited for specific action."""
    client_ip = get_client_ip(request)
    cache_key = f"rate_limit_{action}_{client_ip}"
    attempts = cache.get(cache_key, 0)
    return attempts >= MAX_LOGIN_ATTEMPTS


def increment_rate_limit(request: HttpRequest, action: str = "login") -> None:
    """Increment rate limit counter for client."""
    client_ip = get_client_ip(request)
    cache_key = f"rate_limit_{action}_{client_ip}"
    attempts = cache.get(cache_key, 0)
    cache.set(cache_key, attempts + 1, LOGIN_LOCKOUT_DURATION)


def clear_rate_limit(request: HttpRequest, action: str = "login") -> None:
    """Clear rate limit counter for client."""
    client_ip = get_client_ip(request)
    cache_key = f"rate_limit_{action}_{client_ip}"
    cache.delete(cache_key)


class SecureLoginView(LoginView):
    """
    Enhanced login view with security features.

    Features:
    - Rate limiting protection
    - Account lockout detection
    - Enhanced logging
    - Custom form with remember me functionality
    """

    form_class = SecureLoginForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        # Check rate limiting
        if is_rate_limited(request, "login"):
            logger.warning(f"Rate limited login attempt from {get_client_ip(request)}")
            messages.error(
                request,
                f"Too many failed login attempts. Please try again in "
                f"{LOGIN_LOCKOUT_DURATION // 60} minutes.",
            )
            return render(
                request,
                self.template_name,
                {"form": self.form_class(), "rate_limited": True},
            )

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Handle successful login."""
        # Clear rate limiting on successful login
        clear_rate_limit(self.request, "login")

        # Handle remember me functionality
        if form.cleaned_data.get("remember_me"):
            # Set session to expire in 30 days
            self.request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            # Use default session timeout
            self.request.session.set_expiry(0)

        # Log successful login
        logger.info(
            f"Successful login for user {form.get_user().username} "
            f"from {get_client_ip(self.request)}"
        )

        messages.success(
            self.request,
            f"Welcome back, {form.get_user().first_name or form.get_user().username}!",
        )

        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle failed login."""
        # Increment rate limiting counter
        increment_rate_limit(self.request, "login")

        # Log failed login attempt
        username = form.cleaned_data.get("username", "Unknown")
        logger.warning(
            f"Failed login attempt for username '{username}' "
            f"from {get_client_ip(self.request)}"
        )

        # Don't reveal specific error details
        messages.error(self.request, "Invalid username or password. Please try again.")

        return super().form_invalid(form)


class SecureLogoutView(LogoutView):
    """Enhanced logout view with security features."""

    template_name = "registration/logged_out.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            logger.info(
                f"User {request.user.username} logged out from {get_client_ip(request)}"
            )
        return super().dispatch(request, *args, **kwargs)


class RegistrationView(CreateView):
    """
    Secure user registration view.

    Features:
    - Email verification workflow
    - Role-based registration
    - Enhanced validation
    - Rate limiting protection
    """

    model = User
    form_class = SecureUserRegistrationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("civicpulse:registration_complete")

    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        # Check rate limiting for registration
        if is_rate_limited(request, "registration"):
            messages.error(
                request, "Too many registration attempts. Please try again later."
            )
            return redirect("login")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Handle successful registration."""
        # Clear rate limiting on successful registration
        clear_rate_limit(self.request, "registration")

        # Save user
        user = form.save()

        # Log registration
        logger.info(
            f"New user registered: {user.username} ({user.email}) "
            f"with role {user.role} from {get_client_ip(self.request)}"
        )

        messages.success(
            self.request,
            "Registration successful! Please check your email to verify your account.",
        )

        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle failed registration."""
        # Increment rate limiting counter
        increment_rate_limit(self.request, "registration")

        logger.warning(
            f"Failed registration attempt from {get_client_ip(self.request)}"
        )

        return super().form_invalid(form)


class RegistrationCompleteView(TemplateView):
    """Registration completion page."""

    template_name = "registration/registration_complete.html"


class SecurePasswordResetView(PasswordResetView):
    """Enhanced password reset view with security features."""

    form_class = SecurePasswordResetForm
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("civicpulse:password_reset_done")

    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        # Check rate limiting for password reset
        if is_rate_limited(request, "password_reset"):
            messages.error(
                request, "Too many password reset attempts. Please try again later."
            )
            return redirect("login")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Handle password reset request."""
        # Always show success message to prevent user enumeration
        email = form.cleaned_data["email"]

        # Log password reset attempt
        logger.info(
            f"Password reset requested for email {email} "
            f"from {get_client_ip(self.request)}"
        )

        # Increment rate limiting
        increment_rate_limit(self.request, "password_reset")

        return super().form_valid(form)


class SecurePasswordResetDoneView(PasswordResetDoneView):
    """Password reset done confirmation page."""

    template_name = "registration/password_reset_done.html"


class SecurePasswordResetConfirmView(PasswordResetConfirmView):
    """Enhanced password reset confirmation view."""

    form_class = SecureSetPasswordForm
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("civicpulse:password_reset_complete")

    def form_valid(self, form):
        """Handle successful password reset."""
        user = form.save()

        logger.info(
            f"Password reset completed for user {user.username} "
            f"from {get_client_ip(self.request)}"
        )

        messages.success(
            self.request,
            "Your password has been reset successfully. You can now log in.",
        )

        return super().form_valid(form)


class PasswordResetCompleteView(TemplateView):
    """Password reset completion page."""

    template_name = "registration/password_reset_complete.html"


@method_decorator([csrf_protect, login_required], name="dispatch")
class PasswordChangeView(LoginRequiredMixin, TemplateView):
    """View for authenticated users to change their password."""

    template_name = "registration/password_change.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = PasswordChangeForm(self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        form = PasswordChangeForm(request.user, request.POST)

        if form.is_valid():
            user = form.save()

            # Update the session auth hash to keep user logged in
            from django.contrib.auth import update_session_auth_hash

            update_session_auth_hash(request, user)

            logger.info(
                f"Password changed for user {request.user.username} "
                f"from {get_client_ip(request)}"
            )

            messages.success(request, "Your password has been changed successfully.")

            return redirect("civicpulse:password_change_done")

        return render(request, self.template_name, {"form": form})


class PasswordChangeDoneView(LoginRequiredMixin, TemplateView):
    """Password change completion page."""

    template_name = "registration/password_change_done.html"


@require_http_methods(["GET"])
def account_verification_view(
    request: HttpRequest, uidb64: str, token: str
) -> HttpResponse:
    """
    View to handle email verification links.

    Args:
        request: HTTP request object
        uidb64: Base64 encoded user ID
        token: Email verification token

    Returns:
        HttpResponse with verification result
    """
    try:
        # Decode user ID
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)

        # Verify token
        if default_token_generator.check_token(user, token):
            # Mark user as verified
            user.is_verified = True
            user.save()

            logger.info(
                f"Email verified for user {user.username} from {get_client_ip(request)}"
            )

            messages.success(
                request,
                "Your email has been verified successfully! You can now log in.",
            )

            return redirect("login")
        else:
            raise ValueError("Invalid token")

    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        logger.warning(
            f"Invalid email verification attempt from {get_client_ip(request)}"
        )

        messages.error(request, "The verification link is invalid or has expired.")

        return redirect("registration_complete")


# Dashboard views for different user roles


class DashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard view with role-based content."""

    template_name = "dashboard/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Safely access user attributes
        user_role = getattr(user, "role", None) if user.is_authenticated else None
        organization = (
            getattr(user, "organization", None) if user.is_authenticated else None
        )
        first_name = getattr(user, "first_name", "") if user.is_authenticated else ""
        last_name = getattr(user, "last_name", "") if user.is_authenticated else ""

        context.update(
            {
                "user_role": user_role,
                "organization": organization,
                "user_full_name": f"{first_name} {last_name}".strip()
                or (user.username if user.is_authenticated else ""),
            }
        )

        return context


class ProfileView(LoginRequiredMixin, TemplateView):
    """User profile view."""

    template_name = "dashboard/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        return context


# Health check and monitoring views


def health_check(request):
    """
    Health check endpoint for deployment verification.

    Returns system status including database and cache connectivity.
    """
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "0.1.0",
        "checks": {},
    }

    # Database connectivity check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = f"error: {str(e)}"

    # Cache connectivity check
    try:
        cache.set("health_check", "test", 1)
        cache.get("health_check")
        health_status["checks"]["cache"] = "healthy"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["cache"] = f"error: {str(e)}"

    # Return appropriate HTTP status code
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JsonResponse(health_status, status=status_code)
