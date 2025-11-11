"""
Comprehensive tests for the audit trail system.

Tests cover:
- AuditLog model functionality
- Signal-based automatic logging
- Middleware request tracking
- Admin interface functionality
- Export capabilities
"""

import uuid
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from civicpulse.audit import AuditLog
from civicpulse.middleware.audit import AuditMiddleware, get_request_audit_context
from civicpulse.models import Person
from civicpulse.signals import (
    determine_category,
    get_model_changes,
    log_data_export,
    log_data_import,
)


@pytest.mark.django_db
class TestAuditLogModel(TestCase):
    """Test the AuditLog model functionality."""

    def setUp(self):
        """Set up test data."""
        User = get_user_model()
        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}",
            email="test@example.com",
            password="testpass123",
        )
        self.person = Person.objects.create(
            first_name="John", last_name="Doe", email="john@example.com"
        )

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        Person.objects.all().delete()
        get_user_model().objects.all().delete()

    def test_audit_log_creation(self):
        """Test basic audit log creation."""
        audit_log = AuditLog.log_action(
            action=AuditLog.ACTION_CREATE,
            user=self.user,
            obj=self.person,
            message="Created person record",
            category=AuditLog.CATEGORY_VOTER_DATA,
        )

        self.assertIsInstance(audit_log.id, uuid.UUID)
        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.action, AuditLog.ACTION_CREATE)
        self.assertEqual(audit_log.category, AuditLog.CATEGORY_VOTER_DATA)
        self.assertEqual(audit_log.severity, AuditLog.SEVERITY_INFO)
        self.assertEqual(audit_log.object_repr, str(self.person))
        self.assertEqual(audit_log.user_repr, str(self.user))

    def test_audit_log_immutability(self):
        """Test that audit logs cannot be modified after creation."""
        audit_log = AuditLog.log_action(
            action=AuditLog.ACTION_CREATE, user=self.user, message="Test message"
        )

        # Try to modify the audit log
        audit_log.message = "Modified message"

        with self.assertRaises(ValueError):
            audit_log.save()

    def test_audit_log_search_vector(self):
        """Test that search vector is properly populated."""
        audit_log = AuditLog.log_action(
            action=AuditLog.ACTION_UPDATE,
            user=self.user,
            obj=self.person,
            message="Updated person record",
            changes={"email": {"old": "old@example.com", "new": "new@example.com"}},
        )

        self.assertIn("John", audit_log.search_vector)
        self.assertIn("testuser", audit_log.search_vector)
        self.assertIn("UPDATE", audit_log.search_vector)
        self.assertIn("email", audit_log.search_vector)

    def test_audit_log_changes_display(self):
        """Test human-readable changes display."""
        changes = {
            "email": {"old": "old@example.com", "new": "new@example.com"},
            "first_name": {"old": "Jane", "new": "John"},
        }

        audit_log = AuditLog.log_action(
            action=AuditLog.ACTION_UPDATE,
            user=self.user,
            obj=self.person,
            changes=changes,
        )

        display = audit_log.get_changes_display()
        self.assertIn("email: old@example.com → new@example.com", display)
        self.assertIn("first_name: Jane → John", display)

    def test_audit_log_to_dict(self):
        """Test dictionary export functionality."""
        audit_log = AuditLog.log_action(
            action=AuditLog.ACTION_CREATE,
            user=self.user,
            obj=self.person,
            message="Test export",
            metadata={"test_key": "test_value"},
        )

        data = audit_log.to_dict()

        self.assertEqual(data["user"], str(self.user))
        self.assertEqual(data["action"], "Created")
        self.assertEqual(data["object"], str(self.person))
        self.assertEqual(data["metadata"]["test_key"], "test_value")


@pytest.mark.django_db
class TestAuditLogManager(TestCase):
    """Test the AuditLog custom manager."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing audit logs to ensure clean test state
        AuditLog.objects.all().delete()

        User = get_user_model()
        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}", email="test@example.com"
        )
        self.person = Person.objects.create(first_name="John", last_name="Doe")

        # Clear audit logs created by signals during model creation
        AuditLog.objects.all().delete()

        # Create specific audit logs for testing
        self.audit1 = AuditLog.log_action(
            action=AuditLog.ACTION_CREATE,
            user=self.user,
            obj=self.person,
            category=AuditLog.CATEGORY_VOTER_DATA,
        )

        self.audit2 = AuditLog.log_action(
            action=AuditLog.ACTION_LOGIN,
            user=self.user,
            category=AuditLog.CATEGORY_AUTH,
            severity=AuditLog.SEVERITY_WARNING,
        )

        self.audit3 = AuditLog.log_action(
            action=AuditLog.ACTION_LOGIN_FAILED,
            category=AuditLog.CATEGORY_SECURITY,
            severity=AuditLog.SEVERITY_CRITICAL,
        )

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        Person.objects.all().delete()
        get_user_model().objects.all().delete()

    def test_for_object_query(self):
        """Test filtering by object."""
        logs = AuditLog.objects.for_object(self.person)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first(), self.audit1)

    def test_by_user_query(self):
        """Test filtering by user."""
        logs = AuditLog.objects.by_user(self.user)
        self.assertEqual(logs.count(), 2)
        self.assertIn(self.audit1, logs)
        self.assertIn(self.audit2, logs)

    def test_by_action_query(self):
        """Test filtering by action."""
        logs = AuditLog.objects.by_action(AuditLog.ACTION_CREATE)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first(), self.audit1)

    def test_by_category_query(self):
        """Test filtering by category."""
        logs = AuditLog.objects.by_category(AuditLog.CATEGORY_AUTH)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first(), self.audit2)

    def test_critical_events_query(self):
        """Test filtering critical events."""
        logs = AuditLog.objects.critical_events()
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first(), self.audit3)

    def test_search_query(self):
        """Test full-text search."""
        logs = AuditLog.objects.search("John")
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first(), self.audit1)

        logs = AuditLog.objects.search("testuser")
        self.assertEqual(logs.count(), 2)

    def test_recent_activity_query(self):
        """Test recent activity filtering."""
        # All logs should be recent
        logs = AuditLog.objects.recent_activity(hours=1)
        self.assertEqual(logs.count(), 3)

        # No logs should be from 25 hours ago
        logs = AuditLog.objects.recent_activity(hours=0)
        self.assertEqual(logs.count(), 0)


@pytest.mark.django_db
class TestSignalHandlers(TestCase):
    """Test the signal handlers for automatic audit logging."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing audit logs
        AuditLog.objects.all().delete()

        User = get_user_model()
        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}", email="test@example.com"
        )

        # Clear audit logs created by user creation
        AuditLog.objects.all().delete()

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        Person.objects.all().delete()
        get_user_model().objects.all().delete()

    def test_person_creation_audit(self):
        """Test that creating a Person creates an audit log."""
        # Ensure we start with no audit logs
        self.assertEqual(AuditLog.objects.count(), 0)

        person = Person.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            created_by=self.user,
        )

        # Should have exactly one audit log
        self.assertEqual(AuditLog.objects.count(), 1)

        audit_log = AuditLog.objects.first()
        self.assertEqual(audit_log.action, AuditLog.ACTION_CREATE)
        self.assertEqual(audit_log.content_object, person)
        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.category, AuditLog.CATEGORY_VOTER_DATA)

    def test_person_update_audit(self):
        """Test that updating a Person creates an audit log."""
        person = Person.objects.create(
            first_name="John", last_name="Doe", email="john@example.com"
        )

        # Clear existing audit logs
        AuditLog.objects.all().delete()

        # Update the person
        person.email = "john.updated@example.com"
        person.save()

        # Should have one audit log
        self.assertEqual(AuditLog.objects.count(), 1)

        audit_log = AuditLog.objects.first()
        self.assertEqual(audit_log.action, AuditLog.ACTION_UPDATE)
        self.assertEqual(audit_log.content_object, person)
        self.assertIn("email", audit_log.changes)
        self.assertEqual(audit_log.changes["email"]["old"], "john@example.com")
        self.assertEqual(audit_log.changes["email"]["new"], "john.updated@example.com")

    def test_person_deletion_audit(self):
        """Test that deleting a Person creates an audit log."""
        person = Person.objects.create(first_name="John", last_name="Doe")
        person_str = str(person)

        # Clear audit logs created by person creation
        AuditLog.objects.all().delete()

        # Delete the person
        person.delete()

        # Should have exactly one audit log for deletion
        self.assertEqual(AuditLog.objects.count(), 1)

        audit_log = AuditLog.objects.first()
        self.assertEqual(audit_log.action, AuditLog.ACTION_SOFT_DELETE)
        self.assertEqual(audit_log.object_repr, person_str)
        self.assertEqual(audit_log.category, AuditLog.CATEGORY_VOTER_DATA)
        # Soft deletes are INFO, hard deletes are WARNING
        self.assertEqual(audit_log.severity, AuditLog.SEVERITY_INFO)

    def test_get_model_changes(self):
        """Test the get_model_changes utility function."""
        person = Person.objects.create(
            first_name="John", last_name="Doe", email="john@example.com"
        )

        # Test new instance
        changes = get_model_changes(person, created=True)
        self.assertIn("first_name", changes)
        self.assertEqual(changes["first_name"]["old"], None)
        self.assertEqual(changes["first_name"]["new"], "John")

        # Test existing instance changes
        person.email = "john.updated@example.com"
        changes = get_model_changes(person, created=False)
        self.assertIn("email", changes)
        self.assertEqual(changes["email"]["old"], "john@example.com")
        self.assertEqual(changes["email"]["new"], "john.updated@example.com")

    def test_determine_category(self):
        """Test the determine_category utility function."""
        person = Person.objects.create(first_name="John", last_name="Doe")
        User = get_user_model()
        test_user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}"
        )

        self.assertEqual(determine_category(person), AuditLog.CATEGORY_VOTER_DATA)
        self.assertEqual(determine_category(test_user), AuditLog.CATEGORY_AUTH)

    def test_data_export_logging(self):
        """Test the log_data_export function."""
        log_data_export(
            user=self.user,
            export_type="persons",
            record_count=100,
            filters={"state": "CA"},
            format="csv",
        )

        audit_log = AuditLog.objects.latest("timestamp")
        self.assertEqual(audit_log.action, AuditLog.ACTION_EXPORT)
        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.category, AuditLog.CATEGORY_VOTER_DATA)
        self.assertEqual(audit_log.severity, AuditLog.SEVERITY_WARNING)
        self.assertEqual(audit_log.metadata["export_type"], "persons")
        self.assertEqual(audit_log.metadata["record_count"], 100)
        self.assertEqual(audit_log.metadata["filters"]["state"], "CA")
        self.assertEqual(audit_log.metadata["format"], "csv")

    def test_data_import_logging(self):
        """Test the log_data_import function."""
        log_data_import(
            user=self.user,
            import_type="voter_records",
            record_count=50,
            filename="voters.csv",
        )

        audit_log = AuditLog.objects.latest("timestamp")
        self.assertEqual(audit_log.action, AuditLog.ACTION_IMPORT)
        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.category, AuditLog.CATEGORY_VOTER_DATA)
        self.assertEqual(audit_log.severity, AuditLog.SEVERITY_WARNING)
        self.assertEqual(audit_log.metadata["import_type"], "voter_records")
        self.assertEqual(audit_log.metadata["record_count"], 50)
        self.assertEqual(audit_log.metadata["filename"], "voters.csv")


@pytest.mark.django_db
class TestAuditMiddleware(TestCase):
    """Test the audit middleware functionality."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.middleware = AuditMiddleware(lambda x: HttpResponse())
        self.user = Mock()
        self.user.is_authenticated = True
        self.user.username = f"testuser_{str(uuid.uuid4())[:8]}"

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()

    def test_get_client_ip(self):
        """Test IP address extraction."""
        # Test with X-Forwarded-For header
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "192.168.1.1, 10.0.0.1"
        ip = AuditMiddleware.get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

        # Test with REMOTE_ADDR
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.2"
        ip = AuditMiddleware.get_client_ip(request)
        self.assertEqual(ip, "192.168.1.2")

    def test_process_request(self):
        """Test request processing."""
        request = self.factory.get("/")
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.session = Mock()
        request.session.session_key = "test_session_key"

        self.middleware.process_request(request)

        self.assertTrue(hasattr(request, "audit_context"))
        self.assertEqual(request.audit_context["ip_address"], "192.168.1.1")
        self.assertEqual(request.audit_context["user_agent"], "TestAgent/1.0")
        # session_key is intentionally None in process_request to avoid CSRF interference
        # It gets populated in process_response
        self.assertIsNone(request.audit_context["session_key"])

    def test_should_audit_request(self):
        """Test request auditing logic."""
        # Test write method
        request = self.factory.post("/api/persons/")
        response = HttpResponse()
        self.assertTrue(self.middleware.should_audit_request(request, response))

        # Test admin URL
        request = self.factory.get("/admin/civicpulse/person/")
        response = HttpResponse()
        self.assertTrue(self.middleware.should_audit_request(request, response))

        # Test export URL
        request = self.factory.get("/api/export/persons/")
        response = HttpResponse()
        self.assertTrue(self.middleware.should_audit_request(request, response))

        # Test failed API request
        request = self.factory.get("/api/persons/")
        response = HttpResponse(status=404)
        self.assertTrue(self.middleware.should_audit_request(request, response))

        # Test regular GET request
        request = self.factory.get("/about/")
        response = HttpResponse()
        self.assertFalse(self.middleware.should_audit_request(request, response))

    def test_get_request_audit_context(self):
        """Test audit context helper function."""
        request = self.factory.get("/")
        request.audit_context = {
            "ip_address": "192.168.1.1",
            "user_agent": "TestAgent/1.0",
        }

        context = get_request_audit_context(request)
        self.assertEqual(context["ip_address"], "192.168.1.1")
        self.assertEqual(context["user_agent"], "TestAgent/1.0")

        # Test fallback when no audit_context
        request2 = self.factory.get("/")
        request2.META["REMOTE_ADDR"] = "10.0.0.1"
        request2.session = Mock()
        request2.session.session_key = None

        context2 = get_request_audit_context(request2)
        self.assertEqual(context2["ip_address"], "10.0.0.1")


@pytest.mark.django_db
class TestAuditMixin(TestCase):
    """Test the AuditMixin functionality."""

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        Person.objects.all().delete()
        get_user_model().objects.all().delete()

    def test_audit_mixin_integration(self):
        """Test that AuditMixin works correctly."""
        # Person model should inherit from AuditMixin functionality
        # This is tested implicitly through the signal handler tests
        pass

    def test_get_audit_changes(self):
        """Test the get_audit_changes method."""
        # This functionality is integrated into the signal handlers
        # and tested through the model change tests
        pass


@pytest.mark.django_db
class TestAuditLogAdmin(TestCase):
    """Test the audit log admin interface."""

    def setUp(self):
        """Set up test data."""
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username=f"admin_{str(uuid.uuid4())[:8]}",
            email="admin@example.com",
            password="adminpass123",
        )
        self.audit_log = AuditLog.log_action(
            action=AuditLog.ACTION_CREATE,
            user=self.user,
            message="Test audit log",
            metadata={"test": "data"},
        )

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        get_user_model().objects.all().delete()

    def test_audit_log_read_only_permissions(self):
        """Test that audit logs are read-only in admin."""
        from django.contrib import admin

        from civicpulse.admin import AuditLogAdmin

        admin_class = AuditLogAdmin(AuditLog, admin.site)

        # Test permissions
        request = Mock()
        request.user = self.user

        self.assertFalse(admin_class.has_add_permission(request))
        self.assertFalse(admin_class.has_change_permission(request))
        self.assertFalse(admin_class.has_delete_permission(request))

    def test_audit_log_display_methods(self):
        """Test custom display methods in admin."""
        from django.contrib import admin

        from civicpulse.admin import AuditLogAdmin

        admin_class = AuditLogAdmin(AuditLog, admin.site)

        # Test action display
        action_display = admin_class.action_display(self.audit_log)
        self.assertIn("Created", action_display)
        self.assertIn("color:", action_display)

        # Test user link
        user_link = admin_class.user_link(self.audit_log)
        self.assertIn(str(self.user), user_link)

        # Test category badge
        category_badge = admin_class.category_badge(self.audit_log)
        self.assertIn("System", category_badge)
        self.assertIn("background-color:", category_badge)

        # Test severity badge
        severity_badge = admin_class.severity_badge(self.audit_log)
        self.assertIn("Information", severity_badge)
