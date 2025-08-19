"""
Security monitoring utilities for CivicPulse audit trail system.

This module provides automated detection and alerting for security events including:
- Multiple failed login attempts from the same IP
- Unusual data export activity patterns
- Other suspicious activities that may indicate security threats

All security events are logged to the audit trail and administrators are notified
via email alerts for critical security incidents.
"""

import logging
from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.core.mail import mail_admins
from django.utils import timezone

from civicpulse.audit import AuditLog

User = get_user_model()
logger = logging.getLogger(__name__)

# Configurable security thresholds
DEFAULT_FAILED_LOGIN_THRESHOLD = 5  # failures per hour
DEFAULT_FAILED_LOGIN_WINDOW_HOURS = 1
DEFAULT_EXPORT_THRESHOLD = 10  # exports per day
DEFAULT_EXPORT_WINDOW_HOURS = 24


def check_failed_login_attempts(
    ip_address: str,
    username: str | None = None,
    threshold: int = DEFAULT_FAILED_LOGIN_THRESHOLD,
    window_hours: int = DEFAULT_FAILED_LOGIN_WINDOW_HOURS,
) -> dict[str, Any]:
    """
    Check for excessive failed login attempts from the same IP address.

    This function analyzes recent failed login attempts to detect potential
    brute force attacks or credential stuffing attempts.

    Args:
        ip_address: The IP address to check for failed login attempts
        username: Optional username to include in analysis
        threshold: Number of failed attempts that trigger an alert (default: 5)
        window_hours: Time window in hours to check (default: 1)

    Returns:
        Dictionary containing:
        - alert_triggered: bool indicating if an alert was triggered
        - failure_count: int number of recent failures
        - last_failure_time: datetime of most recent failure
        - metadata: dict with additional context
    """
    try:
        # Calculate the time window
        cutoff_time = timezone.now() - timedelta(hours=window_hours)

        # Query recent failed login attempts from this IP
        recent_failures = AuditLog.objects.filter(
            action=AuditLog.ACTION_LOGIN_FAILED,
            ip_address=ip_address,
            timestamp__gte=cutoff_time,
        ).order_by("-timestamp")

        failure_count = recent_failures.count()
        last_failure = recent_failures.first()

        # Prepare response data
        result = {
            "alert_triggered": False,
            "failure_count": failure_count,
            "last_failure_time": last_failure.timestamp if last_failure else None,
            "metadata": {
                "ip_address": ip_address,
                "username": username,
                "threshold": threshold,
                "window_hours": window_hours,
                "cutoff_time": cutoff_time.isoformat(),
            },
        }

        # Check if threshold is exceeded
        if failure_count >= threshold:
            result["alert_triggered"] = True

            # Get unique usernames attempted (filter out None values)
            attempted_usernames = list(
                recent_failures.values_list(
                    "metadata__username_attempted", flat=True
                ).distinct()
            )
            attempted_usernames = [
                name for name in attempted_usernames if name is not None
            ]
            result["metadata"]["attempted_usernames"] = attempted_usernames

            # Create critical audit log entry
            alert_message = (
                f"SECURITY ALERT: {failure_count} failed login attempts from IP "
                f"{ip_address} in the last {window_hours} hour(s). "
                f"Attempted usernames: {', '.join(attempted_usernames)}"
            )

            critical_audit_log = AuditLog.log_action(
                action=AuditLog.ACTION_LOGIN_FAILED,
                user=None,
                message=alert_message,
                category=AuditLog.CATEGORY_SECURITY,
                severity=AuditLog.SEVERITY_CRITICAL,
                ip_address=ip_address,
                metadata={
                    "alert_type": "multiple_failed_logins",
                    "failure_count": failure_count,
                    "threshold": threshold,
                    "window_hours": window_hours,
                    "attempted_usernames": attempted_usernames,
                    "first_failure_time": recent_failures.last().timestamp.isoformat(),
                    "last_failure_time": last_failure.timestamp.isoformat(),
                },
            )

            # Send email alert to administrators
            subject = (
                f"Security Alert: Multiple Failed Login Attempts from {ip_address}"
            )
            _send_security_alert_email(
                subject=subject,
                message=alert_message,
                additional_context={
                    "ip_address": ip_address,
                    "failure_count": failure_count,
                    "attempted_usernames": attempted_usernames,
                    "audit_log_id": str(critical_audit_log.id),
                },
            )

            logger.critical(alert_message)

        return result

    except Exception as e:
        logger.error(f"Error checking failed login attempts: {e}", exc_info=True)
        return {
            "alert_triggered": False,
            "failure_count": 0,
            "last_failure_time": None,
            "metadata": {"error": str(e)},
        }


def detect_unusual_export_activity(
    user: User,
    threshold: int = DEFAULT_EXPORT_THRESHOLD,
    window_hours: int = DEFAULT_EXPORT_WINDOW_HOURS,
) -> dict[str, Any]:
    """
    Detect unusual data export activity patterns that may indicate data exfiltration.

    This function analyzes recent export operations by a user to identify
    potentially suspicious bulk data extraction attempts.

    Args:
        user: The user to check for export activity
        threshold: Number of exports that trigger an alert (default: 10)
        window_hours: Time window in hours to check (default: 24)

    Returns:
        Dictionary containing:
        - alert_triggered: bool indicating if an alert was triggered
        - export_count: int number of recent exports
        - total_records_exported: int total number of records exported
        - metadata: dict with additional context
    """
    try:
        # Calculate the time window
        cutoff_time = timezone.now() - timedelta(hours=window_hours)

        # Query recent export operations by this user
        recent_exports = AuditLog.objects.filter(
            action=AuditLog.ACTION_EXPORT,
            user=user,
            timestamp__gte=cutoff_time,
        ).order_by("-timestamp")

        export_count = recent_exports.count()

        # Calculate total records exported
        total_records_exported = 0
        export_details = []

        for export_log in recent_exports:
            record_count = export_log.metadata.get("record_count", 0)
            if isinstance(record_count, int | float):
                total_records_exported += int(record_count)

            export_details.append(
                {
                    "timestamp": export_log.timestamp.isoformat(),
                    "record_count": record_count,
                    "export_type": export_log.metadata.get("export_type", "unknown"),
                    "filters": export_log.metadata.get("filters", {}),
                }
            )

        # Prepare response data
        result = {
            "alert_triggered": False,
            "export_count": export_count,
            "total_records_exported": total_records_exported,
            "metadata": {
                "user_id": user.id,
                "username": user.username,
                "threshold": threshold,
                "window_hours": window_hours,
                "cutoff_time": cutoff_time.isoformat(),
                "export_details": export_details[:5],  # Limit to first 5 for brevity
            },
        }

        # Check if threshold is exceeded
        if export_count >= threshold:
            result["alert_triggered"] = True

            # Create critical audit log entry
            alert_message = (
                f"SECURITY ALERT: Unusual export activity detected. "
                f"User {user.username} (ID: {user.id}) performed {export_count} "
                f"export operations in the last {window_hours} hour(s), "
                f"totaling {total_records_exported} records."
            )

            critical_audit_log = AuditLog.log_action(
                action=AuditLog.ACTION_EXPORT,
                user=user,
                message=alert_message,
                category=AuditLog.CATEGORY_SECURITY,
                severity=AuditLog.SEVERITY_CRITICAL,
                metadata={
                    "alert_type": "unusual_export_activity",
                    "export_count": export_count,
                    "total_records_exported": total_records_exported,
                    "threshold": threshold,
                    "window_hours": window_hours,
                    "export_details": export_details,
                },
            )

            # Send email alert to administrators
            _send_security_alert_email(
                subject=f"Security Alert: Unusual Export Activity by {user.username}",
                message=alert_message,
                additional_context={
                    "user_id": user.id,
                    "username": user.username,
                    "export_count": export_count,
                    "total_records_exported": total_records_exported,
                    "audit_log_id": str(critical_audit_log.id),
                },
            )

            logger.critical(alert_message)

        return result

    except Exception as e:
        logger.error(f"Error detecting unusual export activity: {e}", exc_info=True)
        return {
            "alert_triggered": False,
            "export_count": 0,
            "total_records_exported": 0,
            "metadata": {"error": str(e)},
        }


def detect_privilege_escalation_attempts(
    user: User,
    window_hours: int = 24,
) -> dict[str, Any]:
    """
    Detect potential privilege escalation attempts by monitoring permission changes.

    Args:
        user: The user to check for privilege changes
        window_hours: Time window in hours to check (default: 24)

    Returns:
        Dictionary containing alert information
    """
    try:
        # Calculate the time window
        cutoff_time = timezone.now() - timedelta(hours=window_hours)

        # Query recent permission changes for this user
        permission_changes = AuditLog.objects.filter(
            action=AuditLog.ACTION_PERMISSION_CHANGE,
            user=user,
            timestamp__gte=cutoff_time,
        ).order_by("-timestamp")

        change_count = permission_changes.count()

        # Prepare response data
        result = {
            "alert_triggered": False,
            "permission_change_count": change_count,
            "metadata": {
                "user_id": user.id,
                "username": user.username,
                "window_hours": window_hours,
                "cutoff_time": cutoff_time.isoformat(),
            },
        }

        # Check for suspicious activity - any permission changes are investigated
        if change_count > 0:
            result["alert_triggered"] = True

            # Create warning audit log entry
            alert_message = (
                f"SECURITY NOTICE: Permission changes detected for user "
                f"{user.username} (ID: {user.id}). {change_count} permission "
                f"change(s) in the last {window_hours} hour(s)."
            )

            AuditLog.log_action(
                action=AuditLog.ACTION_PERMISSION_CHANGE,
                user=user,
                message=alert_message,
                category=AuditLog.CATEGORY_SECURITY,
                severity=AuditLog.SEVERITY_WARNING,
                metadata={
                    "alert_type": "permission_changes",
                    "change_count": change_count,
                    "window_hours": window_hours,
                },
            )

            logger.warning(alert_message)

        return result

    except Exception as e:
        logger.error(
            f"Error detecting privilege escalation attempts: {e}", exc_info=True
        )
        return {
            "alert_triggered": False,
            "permission_change_count": 0,
            "metadata": {"error": str(e)},
        }


def _send_security_alert_email(
    subject: str,
    message: str,
    additional_context: dict[str, Any] | None = None,
) -> bool:
    """
    Send security alert email to administrators.

    Args:
        subject: Email subject line
        message: Main alert message
        additional_context: Additional context to include in email

    Returns:
        True if email was sent successfully, False otherwise
    """
    try:
        # Build comprehensive email message
        email_body = f"""
CIVICPULSE SECURITY ALERT
========================

{message}

Timestamp: {timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC")}

Additional Details:
"""

        if additional_context:
            for key, value in additional_context.items():
                email_body += f"- {key.replace('_', ' ').title()}: {value}\n"

        email_body += """

Please review the audit logs immediately and take appropriate action if necessary.

This is an automated security alert from the CivicPulse audit trail system.
"""

        # Send email to admins
        mail_admins(
            subject=f"[CivicPulse Security] {subject}",
            message=email_body,
            fail_silently=False,
        )

        logger.info(f"Security alert email sent: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send security alert email: {e}", exc_info=True)
        return False


def get_security_dashboard_data(hours: int = 24) -> dict[str, Any]:
    """
    Get summary data for security dashboard showing recent security events.

    Args:
        hours: Number of hours to look back (default: 24)

    Returns:
        Dictionary with security metrics and recent events
    """
    try:
        cutoff_time = timezone.now() - timedelta(hours=hours)

        # Get critical security events
        critical_events = AuditLog.objects.filter(
            severity=AuditLog.SEVERITY_CRITICAL,
            category=AuditLog.CATEGORY_SECURITY,
            timestamp__gte=cutoff_time,
        ).order_by("-timestamp")

        # Get failed login attempts
        failed_logins = AuditLog.objects.filter(
            action=AuditLog.ACTION_LOGIN_FAILED,
            timestamp__gte=cutoff_time,
        )

        # Get export activity
        exports = AuditLog.objects.filter(
            action=AuditLog.ACTION_EXPORT,
            timestamp__gte=cutoff_time,
        )

        return {
            "timeframe_hours": hours,
            "critical_events_count": critical_events.count(),
            "failed_logins_count": failed_logins.count(),
            "export_operations_count": exports.count(),
            "unique_failed_login_ips": failed_logins.values_list(
                "ip_address", flat=True
            )
            .distinct()
            .count(),
            "recent_critical_events": [
                {
                    "id": str(event.id),
                    "timestamp": event.timestamp.isoformat(),
                    "message": event.message,
                    "ip_address": event.ip_address,
                    "metadata": event.metadata,
                }
                for event in critical_events[:10]  # Last 10 critical events
            ],
        }

    except Exception as e:
        logger.error(f"Error getting security dashboard data: {e}", exc_info=True)
        return {
            "error": str(e),
            "timeframe_hours": hours,
            "critical_events_count": 0,
            "failed_logins_count": 0,
            "export_operations_count": 0,
            "unique_failed_login_ips": 0,
            "recent_critical_events": [],
        }
