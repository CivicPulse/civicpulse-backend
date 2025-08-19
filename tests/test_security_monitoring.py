"""
Comprehensive tests for security monitoring functionality.

Tests cover:
- Failed login attempt detection and alerting
- Unusual export activity detection
- Privilege escalation attempt monitoring
- Email alert functionality
- Security dashboard data
- Threshold configurations and edge cases
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from civicpulse.audit import AuditLog
from civicpulse.utils.security_monitor import (
    check_failed_login_attempts,
    detect_privilege_escalation_attempts,
    detect_unusual_export_activity,
    get_security_dashboard_data,
)

User = get_user_model()


@pytest.mark.django_db
class TestFailedLoginDetection(TestCase):
    """Test failed login attempt detection and alerting."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing audit logs
        AuditLog.objects.all().delete()

        self.ip_address = "192.168.1.100"
        self.username = "test_user"

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()

    def test_no_failed_logins_no_alert(self):
        """Test that no failed logins result in no alert."""
        result = check_failed_login_attempts(
            ip_address=self.ip_address,
            username=self.username
        )

        self.assertFalse(result['alert_triggered'])
        self.assertEqual(result['failure_count'], 0)
        self.assertIsNone(result['last_failure_time'])
        self.assertEqual(result['metadata']['ip_address'], self.ip_address)
        self.assertEqual(result['metadata']['username'], self.username)

    def test_few_failed_logins_no_alert(self):
        """Test that few failed logins don't trigger alert."""
        # Create 3 failed login attempts (below default threshold of 5)
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Failed login attempt {i+1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={'username_attempted': self.username}
            )

        result = check_failed_login_attempts(
            ip_address=self.ip_address,
            username=self.username
        )

        self.assertFalse(result['alert_triggered'])
        self.assertEqual(result['failure_count'], 3)
        self.assertIsNotNone(result['last_failure_time'])

    def test_threshold_exceeded_triggers_alert(self):
        """Test that exceeding threshold triggers security alert."""
        # Create 5 failed login attempts (meets default threshold)
        for i in range(5):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Failed login attempt {i+1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={'username_attempted': self.username}
            )

        with patch('civicpulse.utils.security_monitor.mail_admins') as mock_mail:
            result = check_failed_login_attempts(
                ip_address=self.ip_address,
                username=self.username
            )

        self.assertTrue(result['alert_triggered'])
        self.assertEqual(result['failure_count'], 5)
        self.assertIn(self.username, result['metadata']['attempted_usernames'])

        # Should create critical audit log
        critical_logs = AuditLog.objects.filter(
            severity=AuditLog.SEVERITY_CRITICAL,
            category=AuditLog.CATEGORY_SECURITY
        )
        self.assertEqual(critical_logs.count(), 1)

        critical_log = critical_logs.first()
        self.assertIn('SECURITY ALERT', critical_log.message)
        self.assertIn(str(5), critical_log.message)
        self.assertIn(self.ip_address, critical_log.message)
        self.assertEqual(critical_log.metadata['alert_type'], 'multiple_failed_logins')
        self.assertEqual(critical_log.metadata['failure_count'], 5)

        # Should send email alert
        mock_mail.assert_called_once()
        email_args = mock_mail.call_args
        self.assertIn('Security Alert', email_args[1]['subject'])
        self.assertIn(self.ip_address, email_args[1]['subject'])

    def test_custom_threshold_and_window(self):
        """Test custom threshold and time window settings."""
        # Create 3 failed attempts
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Failed login attempt {i+1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={'username_attempted': self.username}
            )

        # Test with custom threshold of 2 (should trigger)
        result = check_failed_login_attempts(
            ip_address=self.ip_address,
            username=self.username,
            threshold=2,
            window_hours=1
        )

        self.assertTrue(result['alert_triggered'])
        self.assertEqual(result['failure_count'], 3)
        self.assertEqual(result['metadata']['threshold'], 2)

    def test_time_window_filtering(self):
        """Test that time window properly filters old failures."""
        # Create old failed login (outside time window)
        old_time = timezone.now() - timedelta(hours=2)
        with patch('django.utils.timezone.now', return_value=old_time):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message="Old failed login",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={'username_attempted': self.username}
            )

        # Create recent failed logins
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Recent failed login {i+1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={'username_attempted': self.username}
            )

        # Check with 1-hour window
        result = check_failed_login_attempts(
            ip_address=self.ip_address,
            username=self.username,
            window_hours=1
        )

        # Should only count recent failures (3), not old one
        self.assertEqual(result['failure_count'], 3)
        self.assertFalse(result['alert_triggered'])  # Below threshold of 5

    def test_multiple_usernames_attempted(self):
        """Test handling multiple usernames from same IP."""
        usernames = ['admin', 'root', 'user1', 'user2']

        # Create failed attempts for different usernames
        for username in usernames:
            for i in range(2):
                AuditLog.log_action(
                    action=AuditLog.ACTION_LOGIN_FAILED,
                    message=f"Failed login for {username}",
                    category=AuditLog.CATEGORY_SECURITY,
                    ip_address=self.ip_address,
                    metadata={'username_attempted': username}
                )

        result = check_failed_login_attempts(
            ip_address=self.ip_address,
            threshold=5  # 8 total attempts should trigger
        )

        self.assertTrue(result['alert_triggered'])
        self.assertEqual(result['failure_count'], 8)

        # Should include all attempted usernames
        attempted_usernames = result['metadata']['attempted_usernames']
        for username in usernames:
            self.assertIn(username, attempted_usernames)

    def test_exception_handling(self):
        """Test exception handling in failed login detection."""
        with patch('civicpulse.audit.AuditLog.objects.filter', side_effect=Exception('Database error')):
            result = check_failed_login_attempts(
                ip_address=self.ip_address,
                username=self.username
            )

        self.assertFalse(result['alert_triggered'])
        self.assertEqual(result['failure_count'], 0)
        self.assertIn('error', result['metadata'])


@pytest.mark.django_db
class TestUnusualExportActivityDetection(TestCase):
    """Test unusual export activity detection."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing audit logs
        AuditLog.objects.all().delete()

        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}",
            email="test@example.com",
            password="testpass123"
        )

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        User.objects.all().delete()

    def test_no_exports_no_alert(self):
        """Test that no exports result in no alert."""
        result = detect_unusual_export_activity(user=self.user)

        self.assertFalse(result['alert_triggered'])
        self.assertEqual(result['export_count'], 0)
        self.assertEqual(result['total_records_exported'], 0)

    def test_few_exports_no_alert(self):
        """Test that few exports don't trigger alert."""
        # Create 3 export logs (below default threshold of 10)
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=self.user,
                message=f"Export operation {i+1}",
                category=AuditLog.CATEGORY_VOTER_DATA,
                metadata={
                    'export_type': 'persons',
                    'record_count': 100,
                    'format': 'csv'
                }
            )

        result = detect_unusual_export_activity(user=self.user)

        self.assertFalse(result['alert_triggered'])
        self.assertEqual(result['export_count'], 3)
        self.assertEqual(result['total_records_exported'], 300)

    def test_threshold_exceeded_triggers_alert(self):
        """Test that exceeding export threshold triggers alert."""
        # Create 10 export logs (meets default threshold)
        for i in range(10):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=self.user,
                message=f"Export operation {i+1}",
                category=AuditLog.CATEGORY_VOTER_DATA,
                metadata={
                    'export_type': 'persons',
                    'record_count': 500,
                    'format': 'csv'
                }
            )

        with patch('civicpulse.utils.security_monitor.mail_admins') as mock_mail:
            result = detect_unusual_export_activity(user=self.user)

        self.assertTrue(result['alert_triggered'])
        self.assertEqual(result['export_count'], 10)
        self.assertEqual(result['total_records_exported'], 5000)

        # Should create critical audit log
        critical_logs = AuditLog.objects.filter(
            severity=AuditLog.SEVERITY_CRITICAL,
            category=AuditLog.CATEGORY_SECURITY,
            user=self.user
        )
        self.assertEqual(critical_logs.count(), 1)

        critical_log = critical_logs.first()
        self.assertIn('SECURITY ALERT', critical_log.message)
        self.assertIn('Unusual export activity', critical_log.message)
        self.assertIn(self.user.username, critical_log.message)
        self.assertEqual(critical_log.metadata['alert_type'], 'unusual_export_activity')
        self.assertEqual(critical_log.metadata['export_count'], 10)
        self.assertEqual(critical_log.metadata['total_records_exported'], 5000)

        # Should send email alert
        mock_mail.assert_called_once()

    def test_custom_threshold_and_window(self):
        """Test custom threshold and time window settings."""
        # Create 3 export logs
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=self.user,
                message=f"Export operation {i+1}",
                category=AuditLog.CATEGORY_VOTER_DATA,
                metadata={'export_type': 'persons', 'record_count': 100}
            )

        # Test with custom threshold of 2 (should trigger)
        result = detect_unusual_export_activity(
            user=self.user,
            threshold=2,
            window_hours=24
        )

        self.assertTrue(result['alert_triggered'])
        self.assertEqual(result['export_count'], 3)
        self.assertEqual(result['metadata']['threshold'], 2)

    def test_time_window_filtering(self):
        """Test that time window properly filters old exports."""
        # Create old export (outside time window)
        old_time = timezone.now() - timedelta(hours=25)
        with patch('django.utils.timezone.now', return_value=old_time):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=self.user,
                message="Old export",
                category=AuditLog.CATEGORY_VOTER_DATA,
                metadata={'export_type': 'persons', 'record_count': 1000}
            )

        # Create recent exports
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=self.user,
                message=f"Recent export {i+1}",
                category=AuditLog.CATEGORY_VOTER_DATA,
                metadata={'export_type': 'persons', 'record_count': 100}
            )

        # Check with 24-hour window
        result = detect_unusual_export_activity(
            user=self.user,
            window_hours=24
        )

        # Should only count recent exports (3), not old one
        self.assertEqual(result['export_count'], 3)
        self.assertEqual(result['total_records_exported'], 300)  # Not including old 1000

    def test_record_count_calculation(self):
        """Test proper calculation of total records exported."""
        export_data = [
            {'record_count': 100},
            {'record_count': 250},
            {'record_count': 'invalid'},  # Should be ignored
            {'record_count': 75.5},  # Should be converted to int
            {},  # No record_count, should default to 0
        ]

        for i, metadata in enumerate(export_data):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=self.user,
                message=f"Export {i+1}",
                category=AuditLog.CATEGORY_VOTER_DATA,
                metadata=metadata
            )

        result = detect_unusual_export_activity(user=self.user)

        # Should be 100 + 250 + 0 + 75 + 0 = 425
        self.assertEqual(result['total_records_exported'], 425)

    def test_export_details_in_metadata(self):
        """Test that export details are included in alert metadata."""
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=self.user,
                message=f"Export {i+1}",
                category=AuditLog.CATEGORY_VOTER_DATA,
                metadata={
                    'export_type': f'type_{i+1}',
                    'record_count': (i+1) * 100,
                    'filters': {'state': 'CA'}
                }
            )

        result = detect_unusual_export_activity(user=self.user)

        export_details = result['metadata']['export_details']
        self.assertEqual(len(export_details), 3)

        # Check first export details
        first_export = export_details[0]
        self.assertEqual(first_export['export_type'], 'type_3')  # Most recent first
        self.assertEqual(first_export['record_count'], 300)
        self.assertEqual(first_export['filters'], {'state': 'CA'})

    def test_exception_handling(self):
        """Test exception handling in export activity detection."""
        with patch('civicpulse.audit.AuditLog.objects.filter', side_effect=Exception('Database error')):
            result = detect_unusual_export_activity(user=self.user)

        self.assertFalse(result['alert_triggered'])
        self.assertEqual(result['export_count'], 0)
        self.assertEqual(result['total_records_exported'], 0)
        self.assertIn('error', result['metadata'])


@pytest.mark.django_db
class TestPrivilegeEscalationDetection(TestCase):
    """Test privilege escalation attempt monitoring."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing audit logs
        AuditLog.objects.all().delete()

        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}",
            email="test@example.com",
            password="testpass123"
        )

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        User.objects.all().delete()

    def test_no_permission_changes_no_alert(self):
        """Test that no permission changes result in no alert."""
        result = detect_privilege_escalation_attempts(user=self.user)

        self.assertFalse(result['alert_triggered'])
        self.assertEqual(result['permission_change_count'], 0)

    def test_permission_changes_trigger_alert(self):
        """Test that any permission changes trigger security notice."""
        # Create permission change log
        AuditLog.log_action(
            action=AuditLog.ACTION_PERMISSION_CHANGE,
            user=self.user,
            message="Permission granted",
            category=AuditLog.CATEGORY_SECURITY,
            metadata={'permission': 'add_user', 'granted': True}
        )

        result = detect_privilege_escalation_attempts(user=self.user)

        self.assertTrue(result['alert_triggered'])
        self.assertEqual(result['permission_change_count'], 1)

        # Should create warning audit log
        warning_logs = AuditLog.objects.filter(
            severity=AuditLog.SEVERITY_WARNING,
            category=AuditLog.CATEGORY_SECURITY,
            user=self.user,
            action=AuditLog.ACTION_PERMISSION_CHANGE
        )
        self.assertEqual(warning_logs.count(), 2)  # Original + detection log

    def test_time_window_filtering(self):
        """Test that time window properly filters old permission changes."""
        # Create old permission change (outside time window)
        old_time = timezone.now() - timedelta(hours=25)
        with patch('django.utils.timezone.now', return_value=old_time):
            AuditLog.log_action(
                action=AuditLog.ACTION_PERMISSION_CHANGE,
                user=self.user,
                message="Old permission change",
                category=AuditLog.CATEGORY_SECURITY
            )

        # Check with 24-hour window
        result = detect_privilege_escalation_attempts(user=self.user, window_hours=24)

        # Should not count old permission change
        self.assertEqual(result['permission_change_count'], 0)
        self.assertFalse(result['alert_triggered'])

    def test_exception_handling(self):
        """Test exception handling in privilege escalation detection."""
        with patch('civicpulse.audit.AuditLog.objects.filter', side_effect=Exception('Database error')):
            result = detect_privilege_escalation_attempts(user=self.user)

        self.assertFalse(result['alert_triggered'])
        self.assertEqual(result['permission_change_count'], 0)
        self.assertIn('error', result['metadata'])


@pytest.mark.django_db
class TestSecurityDashboard(TestCase):
    """Test security dashboard data functionality."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing audit logs
        AuditLog.objects.all().delete()

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()

    def test_empty_dashboard_data(self):
        """Test dashboard data when no security events exist."""
        result = get_security_dashboard_data(hours=24)

        self.assertEqual(result['timeframe_hours'], 24)
        self.assertEqual(result['critical_events_count'], 0)
        self.assertEqual(result['failed_logins_count'], 0)
        self.assertEqual(result['export_operations_count'], 0)
        self.assertEqual(result['unique_failed_login_ips'], 0)
        self.assertEqual(len(result['recent_critical_events']), 0)

    def test_dashboard_with_security_events(self):
        """Test dashboard data with various security events."""
        # Create critical security events
        for i in range(3):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Critical security event {i+1}",
                category=AuditLog.CATEGORY_SECURITY,
                severity=AuditLog.SEVERITY_CRITICAL,
                ip_address=f"192.168.1.{i+1}",
                metadata={'alert_type': 'security_breach'}
            )

        # Create failed login attempts
        for i in range(5):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Failed login {i+1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=f"10.0.0.{i%2+1}"  # 2 unique IPs
            )

        # Create export operations
        user = User.objects.create_user(username=f"user_{uuid.uuid4()}")
        for i in range(2):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=user,
                message=f"Export operation {i+1}",
                category=AuditLog.CATEGORY_VOTER_DATA
            )

        result = get_security_dashboard_data(hours=24)

        self.assertEqual(result['critical_events_count'], 3)
        self.assertEqual(result['failed_logins_count'], 8)  # 3 critical + 5 regular
        self.assertEqual(result['export_operations_count'], 2)
        self.assertEqual(result['unique_failed_login_ips'], 5)  # 3 from critical + 2 unique from regular
        self.assertEqual(len(result['recent_critical_events']), 3)

        # Check critical event details
        critical_event = result['recent_critical_events'][0]
        self.assertIn('id', critical_event)
        self.assertIn('timestamp', critical_event)
        self.assertIn('message', critical_event)
        self.assertIn('ip_address', critical_event)
        self.assertIn('metadata', critical_event)

    def test_dashboard_time_filtering(self):
        """Test that dashboard properly filters by time window."""
        # Create old events (outside time window)
        old_time = timezone.now() - timedelta(hours=25)
        with patch('django.utils.timezone.now', return_value=old_time):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message="Old failed login",
                category=AuditLog.CATEGORY_SECURITY,
                severity=AuditLog.SEVERITY_CRITICAL
            )

        # Create recent events
        AuditLog.log_action(
            action=AuditLog.ACTION_LOGIN_FAILED,
            message="Recent failed login",
            category=AuditLog.CATEGORY_SECURITY,
            severity=AuditLog.SEVERITY_CRITICAL
        )

        # Check with 24-hour window
        result = get_security_dashboard_data(hours=24)

        # Should only count recent events
        self.assertEqual(result['critical_events_count'], 1)
        self.assertEqual(result['failed_logins_count'], 1)

    def test_dashboard_limits_recent_events(self):
        """Test that dashboard limits recent critical events to 10."""
        # Create 15 critical events
        for i in range(15):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Critical event {i+1}",
                category=AuditLog.CATEGORY_SECURITY,
                severity=AuditLog.SEVERITY_CRITICAL,
                ip_address=f"192.168.1.{i+1}"
            )

        result = get_security_dashboard_data(hours=24)

        self.assertEqual(result['critical_events_count'], 15)
        # Should limit to 10 most recent events
        self.assertEqual(len(result['recent_critical_events']), 10)

    def test_dashboard_exception_handling(self):
        """Test dashboard handles exceptions gracefully."""
        with patch('civicpulse.audit.AuditLog.objects.filter', side_effect=Exception('Database error')):
            result = get_security_dashboard_data(hours=24)

        self.assertIn('error', result)
        self.assertEqual(result['timeframe_hours'], 24)
        self.assertEqual(result['critical_events_count'], 0)
        self.assertEqual(result['failed_logins_count'], 0)
        self.assertEqual(result['export_operations_count'], 0)
        self.assertEqual(result['unique_failed_login_ips'], 0)
        self.assertEqual(len(result['recent_critical_events']), 0)


@pytest.mark.django_db
class TestEmailAlerts(TestCase):
    """Test email alert functionality."""

    def setUp(self):
        """Set up test data."""
        self.ip_address = "192.168.1.100"
        self.username = "test_user"

        # Clear mail outbox
        mail.outbox = []

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()

    def test_failed_login_alert_email(self):
        """Test that failed login alerts send emails."""
        # Create enough failed logins to trigger alert
        for i in range(5):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Failed login attempt {i+1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={'username_attempted': self.username}
            )

        # This should trigger the alert and send email
        result = check_failed_login_attempts(
            ip_address=self.ip_address,
            username=self.username
        )

        self.assertTrue(result['alert_triggered'])

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertIn('Security Alert', email.subject)
        self.assertIn(self.ip_address, email.subject)
        self.assertIn('CIVICPULSE SECURITY ALERT', email.body)
        self.assertIn('failed login attempts', email.body)
        self.assertIn(self.ip_address, email.body)
        self.assertIn(self.username, email.body)

    def test_export_activity_alert_email(self):
        """Test that export activity alerts send emails."""
        user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}",
            email="test@example.com"
        )

        # Create enough exports to trigger alert
        for i in range(10):
            AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=user,
                message=f"Export operation {i+1}",
                category=AuditLog.CATEGORY_VOTER_DATA,
                metadata={'export_type': 'persons', 'record_count': 100}
            )

        result = detect_unusual_export_activity(user=user)

        self.assertTrue(result['alert_triggered'])

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertIn('Security Alert', email.subject)
        self.assertIn(user.username, email.subject)
        self.assertIn('CIVICPULSE SECURITY ALERT', email.body)
        self.assertIn('Unusual export activity', email.body)
        self.assertIn(user.username, email.body)

    @patch('civicpulse.utils.security_monitor.mail_admins')
    def test_email_send_failure_handling(self, mock_mail):
        """Test handling of email send failures."""
        mock_mail.side_effect = Exception('SMTP error')

        # Create failed logins to trigger alert
        for i in range(5):
            AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                message=f"Failed login attempt {i+1}",
                category=AuditLog.CATEGORY_SECURITY,
                ip_address=self.ip_address,
                metadata={'username_attempted': self.username}
            )

        with patch('civicpulse.utils.security_monitor.logger') as mock_logger:
            result = check_failed_login_attempts(
                ip_address=self.ip_address,
                username=self.username
            )

        # Alert should still be triggered
        self.assertTrue(result['alert_triggered'])

        # Should log the email failure
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args[0][0]
        self.assertIn('Failed to send security alert email', error_call)
