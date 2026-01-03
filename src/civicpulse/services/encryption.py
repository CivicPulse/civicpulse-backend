"""
Encryption service for secure token storage in CivicPulse.

Provides Fernet symmetric encryption for OAuth tokens and other sensitive data.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from civicpulse.conf import stripe_settings

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Base exception for encryption-related errors."""

    pass


class EncryptionService:
    """
    Symmetric encryption service using Fernet (AES-128-CBC).

    Encrypts and decrypts sensitive data like OAuth tokens for storage.
    Uses encryption key from civicpulse.conf.stripe_settings.ENCRYPTION_KEY.
    """

    def __init__(self):
        """Initialize the encryption service and validate the key."""
        self._fernet = None
        self._validate_key()

    def _validate_key(self):
        """Validate and initialize the Fernet cipher."""
        key = stripe_settings.ENCRYPTION_KEY
        if not key:
            raise EncryptionError(
                "ENCRYPTION_KEY not configured. Set CIVICPULSE_STRIPE['ENCRYPTION_KEY'] "
                "in Django settings. Generate a key with: "
                "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )

        # Key should be a URL-safe base64-encoded 32-byte key
        if isinstance(key, str):
            key = key.encode()

        try:
            self._fernet = Fernet(key)
            logger.info("Encryption service initialized successfully")
        except Exception as e:
            raise EncryptionError(
                f"Invalid ENCRYPTION_KEY format. Key must be a valid Fernet key "
                f"(URL-safe base64-encoded 32 bytes). Error: {e}"
            ) from e

    def encrypt_token(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string and return base64-encoded ciphertext.

        Args:
            plaintext: The string to encrypt (e.g., OAuth token)

        Returns:
            Base64-encoded ciphertext as a string

        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty string")

        try:
            encrypted_bytes = self._fernet.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt data: {e}") from e

    def decrypt_token(self, ciphertext: str) -> str:
        """
        Decrypt a base64-encoded ciphertext and return plaintext.

        Args:
            ciphertext: Base64-encoded ciphertext string

        Returns:
            Decrypted plaintext string

        Raises:
            EncryptionError: If decryption fails or token is invalid
        """
        if not ciphertext:
            raise EncryptionError("Cannot decrypt empty string")

        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except InvalidToken as e:
            logger.error("Failed to decrypt: Invalid token or wrong key")
            raise EncryptionError(
                "Invalid encrypted token. The data may be corrupted or encrypted with a different key."
            ) from e
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Failed to decrypt data: {e}") from e


# Singleton instance for convenience
_encryption_instance: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get or create the singleton encryption service instance."""
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = EncryptionService()
    return _encryption_instance
