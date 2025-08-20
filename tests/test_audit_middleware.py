"""
Comprehensive tests for audit middleware functionality.

Tests cover:
- Middleware integration with Django request/response cycle
- IP address extraction and forwarded headers
- Request auditing logic and patterns
- Failed login detection and logging
- Security event monitoring
- Middleware configuration and error handling
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from civicpulse.audit import AuditLog
from civicpulse.middleware.audit import AuditMiddleware, get_request_audit_context
from civicpulse.models import Person


@pytest.mark.django_db
class TestAuditMiddlewareIntegration(TestCase):
    """Test middleware integration with Django request/response cycle."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = AuditMiddleware(lambda x: HttpResponse())

        # Clear any existing audit logs
        AuditLog.objects.all().delete()

        User = get_user_model()
        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}",
            email="test@example.com",
            password="testpass123",
        )

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        Person.objects.all().delete()
        get_user_model().objects.all().delete()

    def test_middleware_process_request_anonymous(self):
        """Test middleware processing for anonymous users."""
        request = self.factory.get("/")
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        # Mock session
        request.session = Mock()
        request.session.session_key = "test_session_key"

        self.middleware.process_request(request)

        # Check audit context was added
        self.assertTrue(hasattr(request, "audit_context"))
        self.assertEqual(request.audit_context["ip_address"], "192.168.1.1")
        self.assertEqual(request.audit_context["user_agent"], "TestAgent/1.0")
        self.assertEqual(request.audit_context["session_key"], "test_session_key")

    def test_middleware_process_request_no_session(self):
        """Test middleware processing when no session is available."""
        request = self.factory.get("/")
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        self.middleware.process_request(request)

        self.assertTrue(hasattr(request, "audit_context"))
        self.assertEqual(request.audit_context["ip_address"], "192.168.1.1")
        self.assertEqual(request.audit_context["user_agent"], "TestAgent/1.0")
        self.assertIsNone(request.audit_context["session_key"])

    def test_middleware_post_request_creates_audit_log(self):
        """Test that POST requests create audit logs."""
        # Clear any existing audit logs before the test
        AuditLog.objects.all().delete()

        request = self.factory.post("/api/persons/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        request.session = Mock()
        request.session.session_key = "test_session"

        # Process request and response
        self.middleware.process_request(request)
        response = HttpResponse(status=201)
        self.middleware.process_response(request, response)

        # Check that audit log was created
        self.assertEqual(AuditLog.objects.count(), 1)

        audit_log = AuditLog.objects.first()
        self.assertEqual(audit_log.action, AuditLog.ACTION_CREATE)
        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.ip_address, "192.168.1.1")
        self.assertEqual(audit_log.category, AuditLog.CATEGORY_SYSTEM)
        self.assertIn("POST /api/persons/", audit_log.message)
        self.assertEqual(audit_log.metadata["method"], "POST")
        self.assertEqual(audit_log.metadata["status_code"], 201)

    def test_middleware_admin_request_audit(self):
        """Test that admin requests are audited when they should be."""
        # Test successful admin GET request (should NOT be audited by middleware)
        request = self.factory.get("/admin/civicpulse/person/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=200)
        self.middleware.process_response(request, response)

        # Successful GET requests to admin should NOT be audited by middleware
        # (too noisy)
        audit_logs = AuditLog.objects.all()
        middleware_logs = [log for log in audit_logs if "GET /admin/" in log.message]
        self.assertEqual(
            len(middleware_logs),
            0,
            "Successful admin GET requests should not be audited by middleware",
        )

        # Clear logs and test failed admin request (should be audited)
        AuditLog.objects.all().delete()

        request = self.factory.get("/admin/civicpulse/person/999/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=404)  # Failed request
        self.middleware.process_response(request, response)

        # Failed admin requests SHOULD be audited
        audit_logs = AuditLog.objects.all()
        self.assertEqual(len(audit_logs), 1)

        audit_log = audit_logs[0]
        self.assertEqual(audit_log.category, AuditLog.CATEGORY_ADMIN)
        self.assertIn("/admin/", audit_log.message)
        self.assertEqual(audit_log.severity, AuditLog.SEVERITY_WARNING)

    def test_middleware_export_request_audit(self):
        """Test that export requests are audited when they should be."""
        # Clear any existing audit logs before the test
        AuditLog.objects.all().delete()

        # Test export request that should be audited (contains 'export' in path but
        # not our specific views)
        request = self.factory.get("/api/export/data/?state=CA")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=200)
        self.middleware.process_response(request, response)

        self.assertEqual(AuditLog.objects.count(), 1)

        audit_log = AuditLog.objects.first()
        self.assertEqual(audit_log.action, AuditLog.ACTION_EXPORT)
        self.assertIn("export", audit_log.message.lower())
        # Check that query parameters are captured (but sensitive ones filtered)
        self.assertEqual(audit_log.metadata["query_params"]["state"], "CA")

        # Clear logs and test our specific export view (should NOT be audited by
        # middleware)
        AuditLog.objects.all().delete()

        request = self.factory.get("/export/persons/?state=CA")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=200)
        self.middleware.process_response(request, response)

        # Our specific export views should NOT be audited by middleware (they
        # handle their own logging)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_middleware_failed_api_request_audit(self):
        """Test that failed API requests are audited."""
        # Clear any existing audit logs before the test
        AuditLog.objects.all().delete()

        request = self.factory.get("/api/persons/999/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=404)
        self.middleware.process_response(request, response)

        self.assertEqual(AuditLog.objects.count(), 1)

        audit_log = AuditLog.objects.first()
        self.assertEqual(audit_log.action, AuditLog.ACTION_VIEW)
        self.assertEqual(audit_log.severity, AuditLog.SEVERITY_WARNING)
        self.assertEqual(audit_log.metadata["status_code"], 404)

    def test_middleware_ignores_regular_get_requests(self):
        """Test that regular GET requests are not audited."""
        # Clear any existing audit logs before the test
        AuditLog.objects.all().delete()

        request = self.factory.get("/about/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=200)
        self.middleware.process_response(request, response)

        # Should not create audit log for regular pages
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_middleware_sensitive_query_param_filtering(self):
        """Test that sensitive query parameters are filtered out."""
        # Clear any existing audit logs before the test
        AuditLog.objects.all().delete()

        request = self.factory.get(
            "/api/persons/?password=secret&token=abc123&search=john"
        )
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=404)  # Trigger audit with failed request
        self.middleware.process_response(request, response)

        audit_log = AuditLog.objects.first()
        query_params = audit_log.metadata.get("query_params", {})

        # Sensitive params should be filtered out
        self.assertNotIn("password", query_params)
        self.assertNotIn("token", query_params)
        # Safe params should be included
        self.assertIn("search", query_params)
        self.assertEqual(query_params["search"], "john")


@pytest.mark.django_db
class TestAuditMiddlewareFailedLogins(TestCase):
    """Test failed login detection and security monitoring."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = AuditMiddleware(lambda x: HttpResponse())

        # Clear any existing audit logs
        AuditLog.objects.all().delete()

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()

    def test_failed_login_detection(self):
        """Test that failed login attempts are detected and logged."""
        # Clear any existing audit logs before the test
        AuditLog.objects.all().delete()

        request = self.factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "BruteForcer/1.0"
        request.session = Mock()
        request.session.session_key = "session_123"
        request.POST = {"username": "admin", "password": "wrong"}

        # Set up anonymous user (failed login means no authenticated user)
        request.user = Mock()
        request.user.is_authenticated = False

        self.middleware.process_request(request)
        response = HttpResponse(status=401)  # Failed login

        with patch(
            "civicpulse.utils.security_monitor.check_failed_login_attempts"
        ) as mock_check:
            mock_check.return_value = {
                "alert_triggered": False,
                "failure_count": 1,
                "last_failure_time": None,
                "metadata": {},
            }

            self.middleware.process_response(request, response)

        # Should create audit log for failed login
        self.assertEqual(AuditLog.objects.count(), 1)

        audit_log = AuditLog.objects.first()
        self.assertEqual(audit_log.action, AuditLog.ACTION_LOGIN_FAILED)
        self.assertEqual(audit_log.category, AuditLog.CATEGORY_SECURITY)
        self.assertEqual(audit_log.severity, AuditLog.SEVERITY_WARNING)
        self.assertEqual(audit_log.ip_address, "192.168.1.100")
        self.assertIn("Failed login attempt for username: admin", audit_log.message)
        self.assertEqual(audit_log.metadata["username_attempted"], "admin")

        # Should call security monitoring
        mock_check.assert_called_once_with(ip_address="192.168.1.100", username="admin")

    @patch("civicpulse.utils.security_monitor.check_failed_login_attempts")
    def test_failed_login_security_alert_triggered(self, mock_check):
        """Test behavior when security alert is triggered."""
        mock_check.return_value = {
            "alert_triggered": True,
            "failure_count": 5,
            "last_failure_time": None,
            "metadata": {},
        }

        request = self.factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.POST = {"username": "admin", "password": "wrong"}
        request.session = Mock()
        request.session.session_key = "session_123"

        # Set up anonymous user (failed login means no authenticated user)
        request.user = Mock()
        request.user.is_authenticated = False

        self.middleware.process_request(request)
        response = HttpResponse(status=401)

        with patch("civicpulse.middleware.audit.logger") as mock_logger:
            self.middleware.process_response(request, response)

            # Should log warning about security alert
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args[0][0]
            self.assertIn("Security alert triggered", warning_call)
            self.assertIn("192.168.1.100", warning_call)

    def test_failed_login_missing_username(self):
        """Test failed login handling when username is missing."""
        # Clear any existing audit logs before the test
        AuditLog.objects.all().delete()

        request = self.factory.post("/login/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.session = Mock()
        request.session.session_key = "session_123"
        request.POST = {"password": "wrong"}  # No username

        # Set up anonymous user (failed login means no authenticated user)
        request.user = Mock()
        request.user.is_authenticated = False

        self.middleware.process_request(request)
        response = HttpResponse(status=401)

        with patch(
            "civicpulse.utils.security_monitor.check_failed_login_attempts"
        ) as mock_check:
            mock_check.return_value = {"alert_triggered": False, "failure_count": 1}
            self.middleware.process_response(request, response)

        audit_log = AuditLog.objects.first()
        self.assertIn("Failed login attempt for username: unknown", audit_log.message)
        self.assertEqual(audit_log.metadata["username_attempted"], "unknown")


@pytest.mark.django_db
class TestAuditMiddlewareIPExtraction(TestCase):
    """Test IP address extraction functionality."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

    def test_get_client_ip_x_forwarded_for(self):
        """Test IP extraction from X-Forwarded-For header."""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 192.168.1.1, 10.0.0.1"

        ip = AuditMiddleware.get_client_ip(request)
        self.assertEqual(ip, "203.0.113.1")

    def test_get_client_ip_x_forwarded_for_single(self):
        """Test IP extraction from single X-Forwarded-For header."""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1"

        ip = AuditMiddleware.get_client_ip(request)
        self.assertEqual(ip, "203.0.113.1")

    def test_get_client_ip_remote_addr(self):
        """Test IP extraction from REMOTE_ADDR."""
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        ip = AuditMiddleware.get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

    def test_get_client_ip_no_ip(self):
        """Test IP extraction when no IP is available."""
        request = self.factory.get("/")
        # Clear IP information that the factory might set
        if "REMOTE_ADDR" in request.META:
            del request.META["REMOTE_ADDR"]

        ip = AuditMiddleware.get_client_ip(request)
        self.assertIsNone(ip)

    def test_get_request_audit_context_with_context(self):
        """Test audit context helper when context exists."""
        request = self.factory.get("/")
        request.audit_context = {
            "ip_address": "192.168.1.1",
            "user_agent": "TestAgent/1.0",
            "session_key": "test_session",
        }

        context = get_request_audit_context(request)
        self.assertEqual(context["ip_address"], "192.168.1.1")
        self.assertEqual(context["user_agent"], "TestAgent/1.0")
        self.assertEqual(context["session_key"], "test_session")

    def test_get_request_audit_context_fallback(self):
        """Test audit context helper fallback behavior."""
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        request.META["HTTP_USER_AGENT"] = "FallbackAgent/1.0"
        request.session = Mock()
        request.session.session_key = "fallback_session"

        context = get_request_audit_context(request)
        self.assertEqual(context["ip_address"], "10.0.0.1")
        self.assertEqual(context["user_agent"], "FallbackAgent/1.0")
        self.assertEqual(context["session_key"], "fallback_session")


@pytest.mark.django_db
class TestAuditMiddlewareErrorHandling(TestCase):
    """Test middleware error handling and edge cases."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = AuditMiddleware(lambda x: HttpResponse())

        User = get_user_model()
        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}",
            email="test@example.com",
            password="testpass123",
        )

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        get_user_model().objects.all().delete()

    def test_middleware_no_user(self):
        """Test middleware behavior when request has no user."""
        # Clear any existing audit logs before the test
        AuditLog.objects.all().delete()

        request = self.factory.get("/api/persons/")
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=200)
        result = self.middleware.process_response(request, response)

        # Should not create audit log without user
        self.assertEqual(AuditLog.objects.count(), 0)
        self.assertEqual(result, response)

    def test_middleware_no_audit_context(self):
        """Test middleware behavior when request has no audit context."""
        # Clear any existing audit logs before the test
        AuditLog.objects.all().delete()

        request = self.factory.get("/api/persons/")
        request.user = self.user
        # No audit_context attribute

        response = HttpResponse(status=200)
        result = self.middleware.process_response(request, response)

        # Should not create audit log without audit context
        self.assertEqual(AuditLog.objects.count(), 0)
        self.assertEqual(result, response)

    def test_middleware_anonymous_user_regular_request(self):
        """Test middleware behavior for anonymous users on regular requests."""
        # Clear any existing audit logs before the test
        AuditLog.objects.all().delete()

        request = self.factory.get("/api/persons/")
        request.user = Mock()
        request.user.is_authenticated = False
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=200)
        result = self.middleware.process_response(request, response)

        # Should not create audit log for anonymous user regular requests
        self.assertEqual(AuditLog.objects.count(), 0)
        self.assertEqual(result, response)

    def test_middleware_exception_handling(self):
        """Test middleware handles exceptions gracefully."""
        request = self.factory.post("/api/persons/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=201)

        # Mock an exception in the audit logging process
        with patch(
            "civicpulse.audit.AuditLog.log_action", side_effect=Exception("Test error")
        ):
            with patch("civicpulse.middleware.audit.logger") as mock_logger:
                result = self.middleware.process_response(request, response)

                # Should log the error and continue processing
                mock_logger.error.assert_called_once()
                error_call = mock_logger.error.call_args[0][0]
                self.assertIn("Error logging audit action", error_call)

                # Should return the response normally
                self.assertEqual(result, response)

    def test_middleware_long_user_agent_truncation(self):
        """Test that long user agent strings are truncated."""
        long_user_agent = "A" * 1000  # Create a very long user agent string

        request = self.factory.get("/")
        request.META["HTTP_USER_AGENT"] = long_user_agent
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)

        # User agent should be truncated to 500 characters
        self.assertEqual(len(request.audit_context["user_agent"]), 500)
        self.assertTrue(request.audit_context["user_agent"].startswith("A"))

    def test_action_determination_edge_cases(self):
        """Test action determination for edge cases."""
        # Clear any existing audit logs first
        AuditLog.objects.all().delete()

        # Test our specific export/import paths that should be skipped
        request = self.factory.get("/export/persons/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session"

        self.middleware.process_request(request)
        response = HttpResponse(status=200)

        # Test the _determine_action method to verify the None return
        action = self.middleware._determine_action(request, response)
        self.assertIsNone(action)  # Should return None for our specific export paths

        # This should not create an audit log since action is None
        self.middleware.process_response(request, response)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_category_determination_edge_cases(self):
        """Test category determination for various URL patterns."""
        test_cases = [
            ("/admin/auth/user/", AuditLog.CATEGORY_ADMIN),
            ("/auth/login/", AuditLog.CATEGORY_AUTH),
            ("/login/", AuditLog.CATEGORY_AUTH),
            ("/logout/", AuditLog.CATEGORY_AUTH),
            ("/api/voter-data/", AuditLog.CATEGORY_VOTER_DATA),
            ("/api/contact-info/", AuditLog.CATEGORY_CONTACT),
            ("/api/generic/", AuditLog.CATEGORY_SYSTEM),
            ("/some/other/path/", AuditLog.CATEGORY_SYSTEM),
        ]

        for path, expected_category in test_cases:
            with self.subTest(path=path):
                result = self.middleware._determine_category(path)
                self.assertEqual(result, expected_category)
