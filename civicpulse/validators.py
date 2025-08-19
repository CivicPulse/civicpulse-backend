"""
Custom password validators for enhanced security in the CivicPulse application.

Provides additional password validation beyond Django's built-in validators,
including complexity requirements and password history tracking.
"""

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

User = get_user_model()


class PasswordComplexityValidator:
    """
    Validates password complexity requirements.

    Requires passwords to contain:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """

    def validate(self, password: str, user: User | None = None) -> None:
        """
        Validate password complexity.

        Args:
            password: Password to validate
            user: User instance (optional)

        Raises:
            ValidationError: If password doesn't meet complexity requirements
        """
        errors = []

        # Check for uppercase letter
        if not re.search(r"[A-Z]", password):
            errors.append(_("Password must contain at least one uppercase letter."))

        # Check for lowercase letter
        if not re.search(r"[a-z]", password):
            errors.append(_("Password must contain at least one lowercase letter."))

        # Check for digit
        if not re.search(r"\d", password):
            errors.append(_("Password must contain at least one digit."))

        # Check for special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_+=\-\[\]\\;/`~]', password):
            errors.append(
                _(
                    "Password must contain at least one special character "
                    '(!@#$%^&*(),.?":{}|<>_+=[]\\;/`~).'
                )
            )

        # Check for common weak patterns
        weak_patterns = [
            (
                r"(.)\1{2,}",
                _(
                    "Password cannot contain 3 or more consecutive "
                    "identical characters."
                ),
            ),
            (
                r"(012|123|234|345|456|567|678|789|890)",
                _("Password cannot contain sequential numbers."),
            ),
            (
                r"(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)",
                _("Password cannot contain sequential letters."),
            ),
            (
                r"(qwe|wer|ert|rty|tyu|yui|uio|iop|asd|sdf|dfg|fgh|ghj|hjk|jkl|zxc|xcv|cvb|vbn|bnm)",
                _("Password cannot contain keyboard patterns."),
            ),
        ]

        for pattern, message in weak_patterns:
            if re.search(pattern, password.lower()):
                errors.append(message)

        if errors:
            raise ValidationError(errors)

    def get_help_text(self) -> str:
        """Return help text for password requirements."""
        return _(
            "Your password must contain at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character. "
            "Avoid sequential patterns and repeated characters."
        )


class PasswordHistoryValidator:
    """
    Validates that passwords are not reused from recent history.

    Prevents users from reusing their last N passwords for security.
    """

    def __init__(self, password_history_count: int = 5):
        """
        Initialize validator.

        Args:
            password_history_count: Number of previous passwords to check
        """
        self.password_history_count = password_history_count

    def validate(self, password: str, user: User | None = None) -> None:
        """
        Validate password against history.

        Args:
            password: Password to validate
            user: User instance (optional)

        Raises:
            ValidationError: If password was recently used
        """
        if not user or not user.pk:
            # Can't check history for new users
            return

        # Import here to avoid circular imports
        from civicpulse.models import PasswordHistory

        # Get last N password hashes from history
        recent_passwords = PasswordHistory.objects.filter(
            user=user
        ).order_by('-created_at')[:self.password_history_count]

        # Check if new password matches any recent ones
        for history in recent_passwords:
            if check_password(password, history.password_hash):
                raise ValidationError(
                    _(
                        f"This password has been used recently. "
                        f"Please choose a different password. "
                        f"You cannot reuse any of your last "
                        f"{self.password_history_count} passwords."
                    ),
                    code="password_reused",
                )

    def get_help_text(self) -> str:
        """Return help text for password history requirements."""
        return _(
            f"Your password cannot be the same as any of your last "
            f"{self.password_history_count} passwords."
        )


class PasswordStrengthValidator:
    """
    Validates password strength using entropy-based scoring.

    Calculates password entropy and requires a minimum strength score.
    """

    def __init__(self, min_entropy: int = 60):
        """
        Initialize validator.

        Args:
            min_entropy: Minimum required entropy bits
        """
        self.min_entropy = min_entropy

    def validate(self, password: str, user: User | None = None) -> None:
        """
        Validate password strength.

        Args:
            password: Password to validate
            user: User instance (optional)

        Raises:
            ValidationError: If password is too weak
        """
        entropy = self._calculate_entropy(password)

        if entropy < self.min_entropy:
            raise ValidationError(
                _(
                    f"Password is too weak (entropy: {entropy:.1f} bits). "
                    f"Minimum required: {self.min_entropy} bits."
                ),
                code="password_too_weak",
            )

    def _calculate_entropy(self, password: str) -> float:
        """
        Calculate password entropy in bits.

        Args:
            password: Password to analyze

        Returns:
            Entropy value in bits
        """
        import math

        # Character set sizes
        charset_size = 0

        if re.search(r"[a-z]", password):
            charset_size += 26  # lowercase letters
        if re.search(r"[A-Z]", password):
            charset_size += 26  # uppercase letters
        if re.search(r"\d", password):
            charset_size += 10  # digits
        if re.search(r'[!@#$%^&*(),.?":{}|<>_+=\-\[\]\\;/`~]', password):
            charset_size += 32  # special characters (estimate)

        if charset_size == 0:
            return 0

        # Basic entropy calculation: log2(charset_size) * length
        basic_entropy = math.log2(charset_size) * len(password)

        # Apply penalties for common patterns
        penalty = 0

        # Penalty for repeated characters
        unique_chars = len(set(password))
        if unique_chars < len(password):
            penalty += (len(password) - unique_chars) * 2

        # Penalty for sequential patterns
        if re.search(
            r"(012|123|234|345|456|567|678|789|abc|bcd|cde)", password.lower()
        ):
            penalty += 10

        # Penalty for keyboard patterns
        if re.search(r"(qwe|asd|zxc)", password.lower()):
            penalty += 10

        return max(0, basic_entropy - penalty)

    def get_help_text(self) -> str:
        """Return help text for password strength requirements."""
        return _(
            f"Your password must have sufficient complexity "
            f"(minimum {self.min_entropy} entropy bits). "
            f"Use a mix of character types and avoid patterns."
        )


class CommonPasswordPatternValidator:
    """
    Validates against common password patterns and substitutions.

    Detects and prevents common password patterns like "Password123!"
    even when using character substitutions like "P@ssw0rd123!".
    """

    def __init__(self):
        """Initialize validator with common patterns."""
        # Common substitutions
        self.substitutions = {
            "@": "a",
            "4": "a",
            "3": "e",
            "1": "i",
            "!": "i",
            "0": "o",
            "5": "s",
            "$": "s",
            "7": "t",
            "2": "z",
        }

        # Common password patterns
        self.common_patterns = [
            "password",
            "pass",
            "admin",
            "user",
            "login",
            "welcome",
            "qwerty",
            "asdf",
            "zxcv",
            "letmein",
            "monkey",
            "dragon",
            "football",
            "baseball",
            "basketball",
            "soccer",
            "tennis",
            "master",
            "shadow",
            "michael",
            "jennifer",
            "joshua",
            "hunter",
            "charlie",
            "tigger",
            "thomas",
            "jordan",
        ]

    def validate(self, password: str, user: User | None = None) -> None:
        """
        Validate password against common patterns.

        Args:
            password: Password to validate
            user: User instance (optional)

        Raises:
            ValidationError: If password matches common patterns
        """
        # Convert password to lowercase and reverse substitutions
        normalized = self._normalize_password(password.lower())

        # Check against common patterns
        for pattern in self.common_patterns:
            if pattern in normalized:
                raise ValidationError(
                    _(
                        f'Password contains a common pattern: "{pattern}". '
                        f"Please choose a more unique password."
                    ),
                    code="common_pattern",
                )

        # Check against user attributes if available
        if user:
            user_attrs = [
                getattr(user, "username", "").lower(),
                getattr(user, "first_name", "").lower(),
                getattr(user, "last_name", "").lower(),
                getattr(user, "email", "").split("@")[0].lower(),
                getattr(user, "organization", "").lower(),
            ]

            for attr in user_attrs:
                if attr and len(attr) > 2 and attr in normalized:
                    raise ValidationError(
                        _("Password cannot contain your personal information."),
                        code="personal_info",
                    )

    def _normalize_password(self, password: str) -> str:
        """
        Normalize password by reversing common substitutions.

        Args:
            password: Password to normalize

        Returns:
            Normalized password string
        """
        normalized = password
        for substitute, original in self.substitutions.items():
            normalized = normalized.replace(substitute, original)

        # Remove numbers from the end (common pattern)
        normalized = re.sub(r"\d+$", "", normalized)

        # Remove special characters from the end
        normalized = re.sub(r'[!@#$%^&*(),.?":{}|<>_+=\-\[\]\\;/`~]+$', "", normalized)

        return normalized

    def get_help_text(self) -> str:
        """Return help text for pattern requirements."""
        return _(
            "Your password cannot contain common words, patterns, "
            "or your personal information, even with character substitutions."
        )
