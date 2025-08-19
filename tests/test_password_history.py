"""
Test cases for password history functionality.

This module tests the complete password history system including:
- PasswordHistory model
- Password tracking signals
- PasswordHistoryValidator
- Integration with Django's validation system
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from civicpulse.models import PasswordHistory
from civicpulse.validators import PasswordHistoryValidator

User = get_user_model()


@pytest.mark.django_db
class TestPasswordHistoryModel:
    """Test the PasswordHistory model functionality."""

    def test_password_history_creation(self):
        """Test that PasswordHistory entries can be created."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestP@ssw0rd1!"
        )

        # Manual creation
        history_entry = PasswordHistory.objects.create(
            user=user, password_hash="test_hash"
        )

        assert history_entry.user == user
        assert history_entry.password_hash == "test_hash"
        assert history_entry.created_at is not None

    def test_password_history_string_representation(self):
        """Test the string representation of PasswordHistory."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestP@ssw0rd1!"
        )

        history_entry = PasswordHistory.objects.create(
            user=user, password_hash="test_hash"
        )

        expected_str = (
            f"Password history for {user.username} at {history_entry.created_at}"
        )
        assert str(history_entry) == expected_str

    def test_password_history_ordering(self):
        """Test that password history entries are ordered by creation date."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestP@ssw0rd1!"
        )

        # Create multiple history entries
        entry1 = PasswordHistory.objects.create(user=user, password_hash="hash1")
        entry2 = PasswordHistory.objects.create(user=user, password_hash="hash2")
        entry3 = PasswordHistory.objects.create(user=user, password_hash="hash3")

        # Get all entries - should be in descending order
        entries = list(PasswordHistory.objects.filter(user=user))

        assert entries[0] == entry3  # Most recent first
        assert entries[1] == entry2
        assert entries[2] == entry1  # Oldest last


@pytest.mark.django_db
class TestPasswordHistorySignals:
    """Test password history tracking signals."""

    def test_password_history_on_user_creation(self):
        """Test that password history is created when a user is created."""
        user = User.objects.create_user(
            username="newuser", email="test@example.com", password="TestP@ssw0rd1!"
        )

        # Check that password history was created
        history_count = PasswordHistory.objects.filter(user=user).count()
        assert history_count == 1

        # Check that the password hash matches
        history_entry = PasswordHistory.objects.get(user=user)
        assert history_entry.password_hash == user.password

    def test_password_history_on_password_change(self):
        """Test that password history is updated when password changes."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestP@ssw0rd1!"
        )

        # Initial count should be 1
        assert PasswordHistory.objects.filter(user=user).count() == 1

        # Change password
        user.set_password("TestP@ssw0rd2!")
        user.save()

        # Should have 2 entries now
        assert PasswordHistory.objects.filter(user=user).count() == 2

        # Most recent entry should have the new password
        latest_entry = PasswordHistory.objects.filter(user=user).first()
        assert latest_entry.password_hash == user.password

    def test_password_history_cleanup(self):
        """Test that old password history entries are cleaned up."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestP@ssw0rd1!"
        )

        # Create 12 password changes (initial + 11 more = 12 total)
        for i in range(2, 13):
            user.set_password(f"TestP@ssw0rd{i}!")
            user.save()

        # Should only keep the last 10 entries
        history_count = PasswordHistory.objects.filter(user=user).count()
        assert history_count == 10

    def test_no_history_on_non_password_changes(self):
        """Test that history is not created when non-password fields change."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestP@ssw0rd1!"
        )

        # Initial count should be 1
        assert PasswordHistory.objects.filter(user=user).count() == 1

        # Change non-password field
        user.first_name = "John"
        user.save()

        # Count should still be 1
        assert PasswordHistory.objects.filter(user=user).count() == 1


@pytest.mark.django_db
class TestPasswordHistoryValidator:
    """Test the PasswordHistoryValidator functionality."""

    def test_validator_initialization(self):
        """Test validator initialization with custom history count."""
        validator = PasswordHistoryValidator(password_history_count=3)
        assert validator.password_history_count == 3

    def test_validator_default_initialization(self):
        """Test validator initialization with default history count."""
        validator = PasswordHistoryValidator()
        assert validator.password_history_count == 5

    def test_validator_help_text(self):
        """Test validator help text generation."""
        validator = PasswordHistoryValidator(password_history_count=7)
        expected_text = (
            "Your password cannot be the same as any of your last 7 passwords."
        )
        assert expected_text in validator.get_help_text()

    def test_validate_new_user(self):
        """Test validation for new users (should pass)."""
        validator = PasswordHistoryValidator()

        # New user without pk - should not raise exception
        new_user = User(username="newuser", email="test@example.com")
        validator.validate("TestP@ssw0rd1!", new_user)

        # No user - should not raise exception
        validator.validate("TestP@ssw0rd1!", None)

    def test_validate_password_reuse_prevention(self):
        """Test that recently used passwords are rejected."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestP@ssw0rd1!"
        )

        # Set a few more passwords
        passwords = ["TestP@ssw0rd2!", "TestP@ssw0rd3!", "TestP@ssw0rd4!"]
        for pwd in passwords:
            user.set_password(pwd)
            user.save()

        validator = PasswordHistoryValidator(password_history_count=5)

        # Try to reuse the first password - should fail
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("TestP@ssw0rd1!", user)

        error_message = str(exc_info.value)
        assert "recently" in error_message
        assert "cannot reuse" in error_message

    def test_validate_current_password_rejection(self):
        """Test that the current password is rejected."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestP@ssw0rd1!"
        )

        validator = PasswordHistoryValidator()

        # Try to reuse current password - should fail
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("TestP@ssw0rd1!", user)

        error_message = str(exc_info.value)
        assert "recently" in error_message

    def test_validate_new_password_acceptance(self):
        """Test that new passwords are accepted."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="TestP@ssw0rd1!"
        )

        validator = PasswordHistoryValidator()

        # Try a completely new password - should not raise exception
        validator.validate("CompletelyNewP@ssw0rd!", user)

    def test_validate_old_password_after_history_limit(self):
        """Test that old passwords can be reused after exceeding history limit."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="FirstP@ssw0rd!"
        )

        # Set 6 more passwords (total 7, but history limit is 5)
        for i in range(2, 8):
            user.set_password(f"P@ssw0rd{i}!")
            user.save()

        validator = PasswordHistoryValidator(password_history_count=5)

        # The first password should now be reusable (outside of 5-password limit)
        validator.validate("FirstP@ssw0rd!", user)


@pytest.mark.django_db
class TestPasswordHistoryIntegration:
    """Test integration with Django's password validation system."""

    def test_django_validation_integration(self):
        """Test that the validator works with Django's validate_password function."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="C0mpl3xP@ssw0rd1!"
        )

        # Try to reuse the same password - should fail
        with pytest.raises(ValidationError) as exc_info:
            validate_password("C0mpl3xP@ssw0rd1!", user)

        # Check that history validation error is present
        error_messages = [str(msg) for msg in exc_info.value.error_list]
        history_errors = [msg for msg in error_messages if "recently" in msg]
        assert len(history_errors) > 0

    def test_django_validation_with_valid_new_password(self):
        """Test Django validation with a valid new password."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="C0mpl3xP@ssw0rd1!"
        )

        # Try a new complex password - should not raise ValidationError
        # (unless other validators reject it for different reasons)
        try:
            validate_password("N3wC0mpl3xP@ssw0rd!", user)
        except ValidationError as e:
            # If it fails, it should not be due to password history
            error_messages = [str(msg) for msg in e.error_list]
            history_errors = [msg for msg in error_messages if "recently" in msg]
            assert len(history_errors) == 0

    def test_multiple_users_independent_history(self):
        """Test that password history is independent between users."""
        user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="SharedP@ssw0rd!"
        )
        user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="DifferentP@ssw0rd!"
        )

        validator = PasswordHistoryValidator()

        # User2 should be able to use User1's password
        validator.validate("SharedP@ssw0rd!", user2)

        # User1 should not be able to reuse their own password
        with pytest.raises(ValidationError):
            validator.validate("SharedP@ssw0rd!", user1)
