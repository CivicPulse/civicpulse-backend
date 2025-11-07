"""
Audit middleware for tracking HTTP requests and user actions.

This middleware captures request metadata and provides context for audit logging.
"""

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.urls import Resolver404, resolve
from django.utils.deprecation import MiddlewareMixin

from civicpulse.audit import AuditLog

logger = logging.getLogger(__name__)
User = get_user_model()


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware to track HTTP requests for audit logging.

    This middleware:
    - Captures IP addresses and user agents
    - Tracks sensitive operations
    - Logs security-relevant events
    - Provides request context for audit logs
    """

    # URL patterns that should trigger audit logging
    AUDIT_PATTERNS = [
        "/admin/",
        "/api/export/",
        "/api/import/",
        "/api/voters/",
        "/api/contacts/",
        "/api/users/",
    ]

    # HTTP methods that modify data
    WRITE_METHODS = ["POST", "PUT", "PATCH", "DELETE"]

    def __init__(self, get_response):
        """Initialize the middleware."""
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request: HttpRequest) -> None:
        """
        Process incoming request to capture audit context.

        Args:
            request: The HTTP request object
        """
        # Store audit context in request for later use
        # Note: We don't access session_key here to avoid interfering with
        # CSRF validation
        request.audit_context = {  # type: ignore[attr-defined]
            "ip_address": self.get_client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
            "session_key": None,  # Will be populated in process_response
        }

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """
        Process response to log certain actions.

        Args:
            request: The HTTP request object
            response: The HTTP response object

        Returns:
            The response object
        """
        # Skip if no user or audit context
        if not hasattr(request, "user") or not hasattr(request, "audit_context"):
            return response

        # Safely populate session_key now that CSRF validation has completed
        if hasattr(request, "session") and hasattr(request, "audit_context"):
            try:
                request.audit_context["session_key"] = request.session.session_key  # type: ignore[attr-defined]
            except Exception:
                # Session might not be available in all cases
                pass

        # Skip anonymous users for most logging
        if not request.user.is_authenticated:
            # Only log failed authentication attempts
            if (
                request.path == "/login/"
                and request.method == "POST"
                and response.status_code == 401
            ):
                self._log_failed_login(request)
            return response

        # Check if this request should be audited
        if self.should_audit_request(request, response):
            self._log_request_action(request, response)

        return response

    def should_audit_request(
        self, request: HttpRequest, response: HttpResponse
    ) -> bool:
        """
        Determine if a request should be logged to audit trail.

        Args:
            request: The HTTP request object
            response: The HTTP response object

        Returns:
            True if the request should be audited
        """
        # Always audit write operations
        if request.method in self.WRITE_METHODS:
            return True

        # Audit specific URL patterns
        for pattern in self.AUDIT_PATTERNS:
            if request.path.startswith(pattern):
                return True

        # Audit export/download operations
        if "export" in request.path.lower() or "download" in request.path.lower():
            return True

        # Audit failed requests to sensitive endpoints
        if response.status_code >= 400 and any(
            pattern in request.path for pattern in ["/api/", "/admin/"]
        ):
            return True

        return False

    def _log_request_action(self, request: HttpRequest, response: HttpResponse) -> None:
        """
        Log an HTTP request action to audit trail.

        Args:
            request: The HTTP request object
            response: The HTTP response object
        """
        try:
            # Determine action type based on method and path
            action = self._determine_action(request, response)
            if not action:
                return

            # Determine category based on URL
            category = self._determine_category(request.path)

            # Build metadata
            metadata: dict[str, Any] = {
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
            }

            # Add query parameters for GET requests (be careful with sensitive data)
            if request.method == "GET" and request.GET:
                # Filter out sensitive parameters
                safe_params = {
                    k: v
                    for k, v in request.GET.items()
                    if k not in ["password", "token", "secret", "key"]
                }
                if safe_params:
                    metadata["query_params"] = dict(safe_params)

            # Try to get the view name
            try:
                resolved = resolve(request.path)
                metadata["view_name"] = f"{resolved.view_name}"
            except Resolver404:
                pass

            # Determine severity based on response
            severity = AuditLog.SEVERITY_INFO
            if response.status_code >= 500:
                severity = AuditLog.SEVERITY_ERROR
            elif response.status_code >= 400:
                severity = AuditLog.SEVERITY_WARNING

            # Build message
            message = (
                f"{request.method} {request.path} - Status: {response.status_code}"
            )

            # Create audit log
            AuditLog.log_action(
                action=action,
                user=request.user if request.user.is_authenticated else None,
                message=message,
                category=category,
                severity=severity,
                ip_address=getattr(request, "audit_context", {}).get("ip_address"),
                user_agent=getattr(request, "audit_context", {}).get("user_agent"),
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Error logging audit action: {e}", exc_info=True)

    def _log_failed_login(self, request: HttpRequest) -> None:
        """
        Log a failed login attempt and check for security threats.

        Args:
            request: The HTTP request object
        """
        try:
            username = request.POST.get("username", "unknown")
            ip_address = getattr(request, "audit_context", {}).get("ip_address")

            # Log the individual failed login attempt
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                user=None,
                message=f"Failed login attempt for username: {username}",
                category=AuditLog.CATEGORY_SECURITY,
                severity=AuditLog.SEVERITY_WARNING,
                ip_address=ip_address,
                user_agent=getattr(request, "audit_context", {}).get("user_agent"),
                metadata={
                    "username_attempted": username,
                    "path": request.path,
                },
            )

            # Use security monitoring to check for excessive failed login attempts
            # This creates critical audit logs and sends email alerts if needed
            from civicpulse.utils.security_monitor import check_failed_login_attempts

            security_check = check_failed_login_attempts(
                ip_address=ip_address or "unknown", username=username
            )

            if security_check.get("alert_triggered"):
                logger.warning(
                    f"Security alert triggered for IP {ip_address}: "
                    f"{security_check.get('failure_count')} failed login attempts"
                )

        except Exception as e:
            logger.error(f"Error logging failed login: {e}", exc_info=True)

    def _determine_action(
        self, request: HttpRequest, response: HttpResponse
    ) -> str | None:
        """
        Determine the audit action based on request method and response.

        Args:
            request: The HTTP request object
            response: The HTTP response object

        Returns:
            The action type or None
        """
        # Skip successful GET requests (too noisy)
        if request.method == "GET" and response.status_code < 400:
            # Skip export/import views as they handle audit logging themselves
            if any(
                path in request.path
                for path in ["/export/persons/", "/import/persons/"]
            ):
                return None
            # Only log other exports and sensitive data access
            elif "export" in request.path.lower():
                return AuditLog.ACTION_EXPORT
            elif "download" in request.path.lower():
                return AuditLog.ACTION_EXPORT
            else:
                return None

        # Map HTTP methods to actions
        if response.status_code < 400:  # Successful requests
            # Skip export/import views as they handle audit logging themselves
            if any(
                path in request.path
                for path in ["/export/persons/", "/import/persons/"]
            ):
                return None

            method_action_map = {
                "POST": AuditLog.ACTION_CREATE,
                "PUT": AuditLog.ACTION_UPDATE,
                "PATCH": AuditLog.ACTION_UPDATE,
                "DELETE": AuditLog.ACTION_DELETE,
            }
            return method_action_map.get(request.method or "GET", AuditLog.ACTION_VIEW)

        # For failed requests, just log as VIEW with error
        return AuditLog.ACTION_VIEW

    def _determine_category(self, path: str) -> str:
        """
        Determine the audit category based on URL path.

        Args:
            path: The request path

        Returns:
            The category type
        """
        path_lower = path.lower()

        if "/admin/" in path_lower:
            return AuditLog.CATEGORY_ADMIN
        elif (
            "/auth/" in path_lower or "/login" in path_lower or "/logout" in path_lower
        ):
            return AuditLog.CATEGORY_AUTH
        elif "/voter" in path_lower:
            return AuditLog.CATEGORY_VOTER_DATA
        elif "/contact" in path_lower:
            return AuditLog.CATEGORY_CONTACT
        elif "/api/" in path_lower:
            return AuditLog.CATEGORY_SYSTEM
        else:
            return AuditLog.CATEGORY_SYSTEM

    @staticmethod
    def get_client_ip(request: HttpRequest) -> str | None:
        """
        Get the client's IP address from the request.

        Handles proxy headers appropriately.

        Args:
            request: The HTTP request object

        Returns:
            The client's IP address or None
        """
        # Check for proxy headers
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Take the first IP in the chain
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            # Use direct connection IP
            ip = request.META.get("REMOTE_ADDR")

        return ip


def get_request_audit_context(request: HttpRequest) -> dict:
    """
    Helper function to get audit context from a request.

    Args:
        request: The HTTP request object

    Returns:
        Dictionary with audit context
    """
    if hasattr(request, "audit_context"):
        return getattr(request, "audit_context", {})

    # Fallback if middleware hasn't run
    # Safely access session_key
    session_key = None
    try:
        if hasattr(request, "session"):
            session_key = request.session.session_key
    except Exception:
        # Session might not be available
        pass

    return {
        "ip_address": AuditMiddleware.get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
        "session_key": session_key,
    }
