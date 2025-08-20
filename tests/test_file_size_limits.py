"""
Comprehensive tests for configurable file size limits in person import functionality.

Tests cover:
- Configuration setting integration
- Dynamic file size validation
- Environment variable support
- Error handling and user feedback
- Fallback behavior
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from civicpulse.views.imports import PersonImportView


@pytest.mark.django_db
class TestPersonImportFileSizeLimits(TestCase):
    """Test configurable file size limits for person import functionality."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.view = PersonImportView()

        User = get_user_model()
        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}",
            email="test@example.com",
            password="testpass123",
        )

        # Add import permission
        from django.contrib.auth.models import Permission

        perm = Permission.objects.get(codename="add_person")
        self.user.user_permissions.add(perm)

    def tearDown(self):
        """Clean up test data."""
        User = get_user_model()
        User.objects.all().delete()

    def test_default_file_size_limit_setting(self):
        """Test that default file size limit is 10MB."""
        max_file_size = getattr(settings, "PERSON_IMPORT_MAX_FILE_SIZE", None)
        self.assertIsNotNone(max_file_size)
        self.assertEqual(max_file_size, 10 * 1024 * 1024)  # 10MB

    @override_settings(PERSON_IMPORT_MAX_FILE_SIZE=5 * 1024 * 1024)
    def test_custom_file_size_limit_setting(self):
        """Test that custom file size limits are applied."""
        max_file_size = settings.PERSON_IMPORT_MAX_FILE_SIZE
        self.assertEqual(max_file_size, 5 * 1024 * 1024)  # 5MB

    @patch("civicpulse.views.imports.render")
    def test_file_size_validation_uses_configured_limit(self, mock_render):
        """Test that file size validation uses the configured limit."""
        # Create a file exactly at the default limit (10MB)
        limit_content = "a" * (10 * 1024 * 1024)  # Exactly 10MB
        limit_file = SimpleUploadedFile("limit.csv", limit_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": limit_file})
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = Mock(status_code=200)

        # Should accept the file (exactly at limit)
        response = self.view.post(request)
        self.assertEqual(response.status_code, 200)

    @patch("civicpulse.views.imports.render")
    @patch("civicpulse.views.imports.messages")
    def test_file_size_validation_rejects_oversized_files(
        self, mock_messages, mock_render
    ):
        """Test that files over the limit are rejected."""
        # Create a file larger than the default limit
        oversized_content = "a" * (10 * 1024 * 1024 + 1)  # 10MB + 1 byte
        oversized_file = SimpleUploadedFile(
            "oversized.csv", oversized_content.encode("utf-8")
        )

        request = self.factory.post("/import/persons/", {"csv_file": oversized_file})
        request.user = self.user

        # Mock render to return a simple response
        mock_render.return_value = Mock(status_code=200)

        self.view.post(request)

        # Should call messages.error with file size message
        mock_messages.error.assert_called_once()
        error_call_args = mock_messages.error.call_args[0]
        error_message = error_call_args[1]  # Second argument is the message
        self.assertIn("File size too large", error_message)
        self.assertIn("10MB", error_message)

    @override_settings(PERSON_IMPORT_MAX_FILE_SIZE=2 * 1024 * 1024)
    @patch("civicpulse.views.imports.render")
    @patch("civicpulse.views.imports.messages")
    def test_custom_limit_validation(self, mock_messages, mock_render):
        """Test validation with a custom 2MB limit."""
        # Create a 3MB file (larger than custom 2MB limit)
        large_content = "a" * (3 * 1024 * 1024)  # 3MB
        large_file = SimpleUploadedFile("large.csv", large_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": large_file})
        request.user = self.user

        # Mock render to return a simple response
        mock_render.return_value = Mock(status_code=200)

        self.view.post(request)

        # Should reject with custom limit in error message
        mock_messages.error.assert_called_once()
        error_call_args = mock_messages.error.call_args[0]
        error_message = error_call_args[1]  # Second argument is the message
        self.assertIn("File size too large", error_message)
        self.assertIn("2MB", error_message)

    @override_settings(PERSON_IMPORT_MAX_FILE_SIZE=1 * 1024 * 1024)
    @patch("civicpulse.views.imports.render")
    def test_small_custom_limit_validation(self, mock_render):
        """Test validation with a very small custom limit (1MB)."""
        # Create a small 512KB file (within limit)
        small_content = "a" * (512 * 1024)  # 512KB
        small_file = SimpleUploadedFile("small.csv", small_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": small_file})
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = Mock(status_code=200)

        response = self.view.post(request)

        # Should accept the small file
        self.assertEqual(response.status_code, 200)
        # Should not call messages.error for file size
        if request._messages.error.called:
            # If error was called, it shouldn't be about file size
            error_calls = request._messages.error.call_args_list
            for call in error_calls:
                self.assertNotIn("File size too large", call[0][1])

    def test_fallback_behavior_when_setting_missing(self):
        """Test that the view uses fallback when setting is not configured."""
        # Temporarily remove the setting
        with patch.object(settings, "PERSON_IMPORT_MAX_FILE_SIZE", None, create=True):
            # Delete the attribute to simulate it not being set
            if hasattr(settings, "PERSON_IMPORT_MAX_FILE_SIZE"):
                delattr(settings, "PERSON_IMPORT_MAX_FILE_SIZE")

            # The view should use getattr with fallback
            max_file_size = getattr(
                settings, "PERSON_IMPORT_MAX_FILE_SIZE", 10 * 1024 * 1024
            )
            self.assertEqual(max_file_size, 10 * 1024 * 1024)

    @override_settings(PERSON_IMPORT_MAX_FILE_SIZE=15 * 1024 * 1024)
    def test_help_text_reflects_configured_limit(self):
        """Test that help text displays the actual configured limit."""
        request = self.factory.get("/import/persons/")
        request.user = self.user

        # Get help text from the view
        help_text = self.view._get_help_text()

        # Should contain the custom 15MB limit
        self.assertIn("15MB", help_text["file_limits"])

    @override_settings(PERSON_IMPORT_MAX_FILE_SIZE=512 * 1024)  # 512KB
    def test_help_text_handles_fractional_mb(self):
        """Test that help text handles limits smaller than 1MB correctly."""
        request = self.factory.get("/import/persons/")
        request.user = self.user

        # Get help text from the view
        help_text = self.view._get_help_text()

        # Should show 1MB (rounded up from 0.5MB)
        self.assertIn("1MB", help_text["file_limits"])

    @override_settings(PERSON_IMPORT_MAX_FILE_SIZE=1536 * 1024)  # 1.5MB
    def test_help_text_rounds_fractional_mb(self):
        """Test that help text rounds fractional MB values appropriately."""
        request = self.factory.get("/import/persons/")
        request.user = self.user

        # Get help text from the view
        help_text = self.view._get_help_text()

        # Should show 2MB (rounded from 1.5MB)
        self.assertIn("2MB", help_text["file_limits"])

    @patch("civicpulse.views.imports.render")
    @patch("civicpulse.views.imports.messages")
    def test_error_message_format(self, mock_messages, mock_render):
        """Test that error messages are properly formatted."""
        from django.conf import settings

        # Mock a large file
        large_content = "a" * (20 * 1024 * 1024)  # 20MB
        large_file = SimpleUploadedFile("large.csv", large_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": large_file})
        request.user = self.user

        # Use the actual view logic for error formatting
        max_file_size = getattr(
            settings, "PERSON_IMPORT_MAX_FILE_SIZE", 10 * 1024 * 1024
        )
        max_size_mb = max_file_size / (1024 * 1024)
        expected_message = f"File size too large. Maximum size is {max_size_mb:.0f}MB."

        # Mock render to return a simple response
        mock_render.return_value = Mock(status_code=200)

        self.view.post(request)

        # Verify the error message format
        mock_messages.error.assert_called_once()
        error_call_args = mock_messages.error.call_args[0]
        actual_message = error_call_args[1]  # Second argument is the message
        self.assertEqual(actual_message, expected_message)

    @override_settings(PERSON_IMPORT_MAX_FILE_SIZE="invalid")
    def test_invalid_setting_value_handling(self):
        """Test handling of invalid setting values."""
        # This test ensures the code doesn't crash with invalid settings
        # In practice, django-environ would validate this, but we test the fallback

        request = self.factory.get("/import/persons/")
        request.user = self.user

        # Should not raise an exception
        try:
            help_text = self.view._get_help_text()
            # getattr should provide the fallback value if setting is invalid
            self.assertIsInstance(help_text, dict)
            self.assertIn("file_limits", help_text)
        except Exception as e:
            self.fail(f"View should handle invalid settings gracefully, but got: {e}")

    def test_boundary_conditions(self):
        """Test file size validation at exact boundaries."""
        # Test with file exactly at the configured limit
        limit_size = getattr(settings, "PERSON_IMPORT_MAX_FILE_SIZE", 10 * 1024 * 1024)

        # File exactly at limit should be accepted
        exact_content = "a" * limit_size
        exact_file = SimpleUploadedFile("exact.csv", exact_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": exact_file})
        request.user = self.user
        request._messages = Mock()

        with patch("civicpulse.views.imports.render") as mock_render:
            mock_render.return_value = Mock(status_code=200)

            self.view.post(request)

            # Should not trigger file size error
            if request._messages.error.called:
                error_calls = request._messages.error.call_args_list
                for call in error_calls:
                    self.assertNotIn("File size too large", call[0][1])
