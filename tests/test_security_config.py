"""
Tests for configurable security monitoring thresholds.

This module tests that security thresholds can be configured via Django settings
and that the security monitoring functions respect these custom configurations.
"""

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from civicpulse.audit import AuditLog
from civicpulse.utils.security_monitor import (
    check_failed_login_attempts,
    detect_privilege_escalation_attempts,
    detect_unusual_export_activity,
    get_export_threshold,
    get_export_window_hours,
    get_failed_login_threshold,
    get_failed_login_window_hours,
    get_privilege_escalation_window_hours,
)

User = get_user_model()


@pytest.mark.django_db
class TestSecurityThresholdConfiguration(TestCase):
    """Test configurable security threshold settings."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing audit logs
        AuditLog.objects.all().delete()

        self.ip_address = "192.168.1.100"
        self.username = "test_user"
        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}",
            email="test@example.com",
            password="testpass123",
        )

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        User.objects.all().delete()

    def test_default_threshold_getters(self):
        """Test that threshold getters return default values when no settings are
        configured."""
        # Test without any custom settings
        self.assertEqual(get_failed_login_threshold(), 5)
        self.assertEqual(get_failed_login_window_hours(), 1)
        self.assertEqual(get_export_threshold(), 10)
        self.assertEqual(get_export_window_hours(), 24)
        self.assertEqual(get_privilege_escalation_window_hours(), 24)

    @override_settings(
        SECURITY_FAILED_LOGIN_THRESHOLD=3,
        SECURITY_FAILED_LOGIN_WINDOW_HOURS=2,
        SECURITY_EXPORT_THRESHOLD=5,
        SECURITY_EXPORT_WINDOW_HOURS=12,
        SECURITY_PRIVILEGE_ESCALATION_WINDOW_HOURS=48,
    )
    def test_custom_threshold_getters(self):
        """Test that threshold getters return custom values when settings are
        configured."""
        self.assertEqual(get_failed_login_threshold(), 3)
        self.assertEqual(get_failed_login_window_hours(), 2)
        self.assertEqual(get_export_threshold(), 5)
        self.assertEqual(get_export_window_hours(), 12)
        self.assertEqual(get_privilege_escalation_window_hours(), 48)

    @override_settings(SECURITY_FAILED_LOGIN_THRESHOLD=3)
    def test_failed_login_uses_custom_threshold(self):
        """Test that failed login detection uses custom threshold from settings."""
        # Create 3 failed login attempts (should trigger with custom threshold of 3)
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Failed login attempt {i + 1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={"username_attempted": self.username},
            )

        # Should trigger alert with custom threshold
        result = check_failed_login_attempts(ip_address=self.ip_address)
        self.assertTrue(result["alert_triggered"])
        self.assertEqual(result["failure_count"], 3)
        self.assertEqual(result["metadata"]["threshold"], 3)

    @override_settings(SECURITY_EXPORT_THRESHOLD=3)
    def test_export_activity_uses_custom_threshold(self):
        """Test that export activity detection uses custom threshold from settings."""
        # Create 3 export logs (should trigger with custom threshold of 3)
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=self.user,
                message=f"Export operation {i + 1}",
                category=AuditLog.CATEGORY_VOTER_DATA,
                metadata={
                    "export_type": "persons",
                    "record_count": 100,
                    "format": "csv",
                },
            )

        # Should trigger alert with custom threshold
        result = detect_unusual_export_activity(user=self.user)
        self.assertTrue(result["alert_triggered"])
        self.assertEqual(result["export_count"], 3)
        self.assertEqual(result["metadata"]["threshold"], 3)

    @override_settings(SECURITY_PRIVILEGE_ESCALATION_WINDOW_HOURS=1)
    def test_privilege_escalation_uses_custom_window(self):
        """Test that privilege escalation detection uses custom window from settings."""
        # Create a permission change log
        AuditLog.log_action(
            action=AuditLog.ACTION_PERMISSION_CHANGE,
            user=self.user,
            message="Permission granted",
            category=AuditLog.CATEGORY_SECURITY,
            metadata={"permission": "add_user", "granted": True},
        )

        result = detect_privilege_escalation_attempts(user=self.user)
        self.assertTrue(result["alert_triggered"])
        self.assertEqual(result["metadata"]["window_hours"], 1)

    def test_explicit_parameters_override_settings(self):
        """Test that explicit parameters override settings when provided."""
        # Create 2 failed login attempts
        for i in range(2):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Failed login attempt {i + 1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={"username_attempted": self.username},
            )

        # Explicitly pass threshold=1 (should trigger even though default is 5)
        result = check_failed_login_attempts(
            ip_address=self.ip_address, threshold=1, window_hours=1
        )

        self.assertTrue(result["alert_triggered"])
        self.assertEqual(result["failure_count"], 2)
        self.assertEqual(result["metadata"]["threshold"], 1)
        self.assertEqual(result["metadata"]["window_hours"], 1)

    @override_settings(SECURITY_FAILED_LOGIN_THRESHOLD=10)
    def test_backward_compatibility_with_explicit_params(self):
        """Test that explicit parameters still work when settings are configured."""
        # Create 3 failed login attempts
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Failed login attempt {i + 1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={"username_attempted": self.username},
            )

        # Test with settings configured but explicit parameters provided
        result = check_failed_login_attempts(
            ip_address=self.ip_address,
            threshold=2,  # Should use this instead of settings value of 10
        )

        self.assertTrue(result["alert_triggered"])
        self.assertEqual(result["metadata"]["threshold"], 2)

    def test_missing_settings_graceful_fallback(self):
        """Test that missing settings gracefully fall back to defaults."""
        # Mock settings to not have the security settings
        with patch("civicpulse.utils.security_monitor.settings") as mock_settings:
            # Make settings not have our custom attributes
            mock_settings.configure_mock(**{})
            del mock_settings.SECURITY_FAILED_LOGIN_THRESHOLD
            del mock_settings.SECURITY_FAILED_LOGIN_WINDOW_HOURS

            # Should still work with defaults
            self.assertEqual(get_failed_login_threshold(), 5)
            self.assertEqual(get_failed_login_window_hours(), 1)

    @override_settings(
        SECURITY_FAILED_LOGIN_THRESHOLD=2,
        SECURITY_FAILED_LOGIN_WINDOW_HOURS=3,
    )
    def test_all_functions_respect_settings(self):
        """Test that all security monitoring functions respect their respective
        settings."""
        # Create just enough activity to test settings are being used

        # Failed logins - should trigger with threshold 2
        for i in range(2):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Failed login {i + 1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={"username_attempted": self.username},
            )

        # Check that custom settings are respected in function calls
        result = check_failed_login_attempts(ip_address=self.ip_address)

        # Should trigger because we have 2 attempts and threshold is 2
        self.assertTrue(result["alert_triggered"])
        self.assertEqual(result["metadata"]["threshold"], 2)
        self.assertEqual(result["metadata"]["window_hours"], 3)

    @override_settings(SECURITY_EXPORT_THRESHOLD=2, SECURITY_EXPORT_WINDOW_HOURS=6)
    def test_export_settings_integration(self):
        """Test export monitoring integrates properly with settings."""
        # Create 2 exports to match threshold
        for i in range(2):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=self.user,
                message=f"Export {i + 1}",
                category=AuditLog.CATEGORY_VOTER_DATA,
                metadata={"export_type": "persons", "record_count": 100},
            )

        result = detect_unusual_export_activity(user=self.user)

        self.assertTrue(result["alert_triggered"])
        self.assertEqual(result["metadata"]["threshold"], 2)
        self.assertEqual(result["metadata"]["window_hours"], 6)
