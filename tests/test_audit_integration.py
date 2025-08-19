"""
Test the integration between current user middleware and audit trail.
"""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TransactionTestCase

from civicpulse.audit import AuditLog
from civicpulse.middleware.current_user import (
    CurrentUserMiddleware,
    clear_current_user,
    get_current_user,
)
from civicpulse.models import Person

User = get_user_model()


class TestAuditIntegration(TransactionTestCase):
    """Test that audit trail captures users through middleware."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

        def get_response(request):
            return None

        self.middleware = CurrentUserMiddleware(get_response)

        # Clear any existing user
        clear_current_user()

    def test_audit_captures_current_user_from_middleware(self):
        """Test that audit logs capture the user when set via middleware."""
        # Create a user
        user = User.objects.create_user(
            username="audit_user",
            email="audit@example.com",
            password="testpass123"
        )

        # Create a request with the user
        request = self.factory.get("/")
        request.user = user

        # Process the request through middleware
        self.middleware.process_request(request)

        # Verify the user is accessible
        assert get_current_user() == user

        # Create a person (which should trigger audit logging)
        person = Person.objects.create(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com"
        )

        # Check that an audit log was created with the user
        from django.contrib.contenttypes.models import ContentType
        person_content_type = ContentType.objects.get_for_model(Person)
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_CREATE,
            content_type=person_content_type,
            object_id=str(person.id)
        )

        self.assertEqual(audit_logs.count(), 1)
        audit_log = audit_logs.first()
        self.assertEqual(audit_log.user, user)
        self.assertIn("Created Person", audit_log.message)

        # Clean up
        self.middleware.process_response(request, None)
        assert get_current_user() is None

    def test_audit_without_user_still_works(self):
        """Test that audit logging still works when no user is set."""
        # Don't set any user
        clear_current_user()
        assert get_current_user() is None

        # Create a person (which should trigger audit logging)
        person = Person.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com"
        )

        # Check that an audit log was created without a user
        from django.contrib.contenttypes.models import ContentType
        person_content_type = ContentType.objects.get_for_model(Person)
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_CREATE,
            content_type=person_content_type,
            object_id=str(person.id)
        )

        self.assertEqual(audit_logs.count(), 1)
        audit_log = audit_logs.first()
        self.assertIsNone(audit_log.user)
        self.assertIn("Created Person", audit_log.message)
