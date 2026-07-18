import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken


class TokenEncryption:
    def __init__(self, secret_key: str):
        # Derive a 32-byte URL-safe base64-encoded Fernet key from any secret.
        digest = hashlib.sha256(secret_key.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Invalid token or wrong encryption key") from exc


def get_encryptor() -> TokenEncryption:
    from config import settings
    return TokenEncryption(settings.SECRET_KEY)
