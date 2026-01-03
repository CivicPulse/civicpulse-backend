"""Tests for encryption service."""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from civicpulse.services.encryption import (
    EncryptionError,
    EncryptionService,
    get_encryption_service,
)


class TestEncryptionService:
    """Test suite for EncryptionService using pytest."""

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_encrypt_decrypt_roundtrip(self, mock_settings):
        """Test that encrypted data can be decrypted correctly."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()
        service = EncryptionService()
        plaintext = "sk_test_123456789"

        ciphertext = service.encrypt_token(plaintext)
        decrypted = service.decrypt_token(ciphertext)

        assert plaintext == decrypted
        assert plaintext != ciphertext

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_encrypt_produces_different_ciphertext(self, mock_settings):
        """Test that encrypting the same plaintext twice produces different ciphertext."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()
        service = EncryptionService()
        plaintext = "sensitive_token"

        ciphertext1 = service.encrypt_token(plaintext)
        ciphertext2 = service.encrypt_token(plaintext)

        # Fernet includes a timestamp, so ciphertext should differ
        assert ciphertext1 != ciphertext2
        # But both should decrypt to the same value
        assert service.decrypt_token(ciphertext1) == plaintext
        assert service.decrypt_token(ciphertext2) == plaintext

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_missing_encryption_key_raises_error(self, mock_settings):
        """Test that missing encryption key raises EncryptionError."""
        mock_settings.ENCRYPTION_KEY = None

        with pytest.raises(EncryptionError, match="ENCRYPTION_KEY not configured"):
            EncryptionService()

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_invalid_encryption_key_raises_error(self, mock_settings):
        """Test that invalid encryption key format raises EncryptionError."""
        mock_settings.ENCRYPTION_KEY = "invalid_key"

        with pytest.raises(EncryptionError, match="Invalid ENCRYPTION_KEY format"):
            EncryptionService()

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_encrypt_empty_string_raises_error(self, mock_settings):
        """Test that encrypting empty string raises EncryptionError."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()
        service = EncryptionService()

        with pytest.raises(EncryptionError, match="Cannot encrypt empty string"):
            service.encrypt_token("")

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_decrypt_empty_string_raises_error(self, mock_settings):
        """Test that decrypting empty string raises EncryptionError."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()
        service = EncryptionService()

        with pytest.raises(EncryptionError, match="Cannot decrypt empty string"):
            service.decrypt_token("")

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_decrypt_invalid_ciphertext_raises_error(self, mock_settings):
        """Test that decrypting invalid ciphertext raises EncryptionError."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()
        service = EncryptionService()

        with pytest.raises(EncryptionError, match="Invalid encrypted token"):
            service.decrypt_token("invalid_ciphertext")

    def test_decrypt_with_wrong_key_raises_error(self):
        """Test that decrypting with wrong key raises EncryptionError."""
        # Encrypt with one key
        key1 = Fernet.generate_key().decode()
        with patch("civicpulse.services.encryption.stripe_settings") as mock_settings:
            mock_settings.ENCRYPTION_KEY = key1
            service1 = EncryptionService()
            ciphertext = service1.encrypt_token("secret")

        # Try to decrypt with different key
        key2 = Fernet.generate_key().decode()
        with patch("civicpulse.services.encryption.stripe_settings") as mock_settings:
            mock_settings.ENCRYPTION_KEY = key2
            service2 = EncryptionService()

            with pytest.raises(EncryptionError, match="Invalid encrypted token"):
                service2.decrypt_token(ciphertext)

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_encrypt_long_string(self, mock_settings):
        """Test encrypting and decrypting a long string."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()
        service = EncryptionService()
        plaintext = "x" * 10000  # 10KB string

        ciphertext = service.encrypt_token(plaintext)
        decrypted = service.decrypt_token(ciphertext)

        assert plaintext == decrypted

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_encrypt_unicode_string(self, mock_settings):
        """Test encrypting and decrypting Unicode characters."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()
        service = EncryptionService()
        plaintext = "Hello 世界 🌍 café"

        ciphertext = service.encrypt_token(plaintext)
        decrypted = service.decrypt_token(ciphertext)

        assert plaintext == decrypted

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_singleton_get_encryption_service(self, mock_settings):
        """Test that get_encryption_service returns singleton instance."""
        mock_settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

        # Reset the singleton
        import civicpulse.services.encryption as encryption_module

        encryption_module._encryption_instance = None

        service1 = get_encryption_service()
        service2 = get_encryption_service()

        assert service1 is service2

    @patch("civicpulse.services.encryption.stripe_settings")
    def test_encryption_key_as_bytes(self, mock_settings):
        """Test that encryption key works when provided as bytes."""
        key_bytes = Fernet.generate_key()
        mock_settings.ENCRYPTION_KEY = key_bytes

        service = EncryptionService()
        plaintext = "test_token"

        ciphertext = service.encrypt_token(plaintext)
        decrypted = service.decrypt_token(ciphertext)

        assert plaintext == decrypted
