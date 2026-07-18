import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken


class TokenEncryption:
    """Encrypt and decrypt short text tokens using a Fernet-derived key.

    A Fernet key is deterministically derived from the provided secret key
    using SHA-256, so the same secret always produces the same key.
    """

    def __init__(self, secret_key: str):
        """Create a Fernet encryptor from a secret key.

        Args:
            secret_key: The secret key used to derive the Fernet key.
        """
        # Derive a 32-byte URL-safe base64-encoded Fernet key from any secret.
        digest = hashlib.sha256(secret_key.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt.

        Returns:
            The encrypted ciphertext, or an empty string if plaintext is empty.
        """
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string.

        Args:
            ciphertext: The string to decrypt.

        Returns:
            The decrypted plaintext, or an empty string if ciphertext is empty.

        Raises:
            ValueError: If the ciphertext is invalid or was encrypted with a
                different key.
        """
        if not ciphertext:
            return ""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Invalid token or wrong encryption key") from exc


def get_encryptor() -> TokenEncryption:
    """Return a TokenEncryption instance using the configured SECRET_KEY."""
    from config import settings
    return TokenEncryption(settings.SECRET_KEY)
