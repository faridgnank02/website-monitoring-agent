"""Per-site token encryption for integration credentials.

Each site derives its own Fernet key from the master SECRET_KEY and the
site id (HMAC-SHA256), so a compromise of one site's ciphertext does not
expose other sites' tokens.
"""

import hashlib
import hmac
from typing import Optional

from core.security.encryption import TokenEncryption


def _master_key() -> str:
    from config import settings
    if not settings.SECRET_KEY or not settings.SECRET_KEY.strip():
        raise ValueError("SECRET_KEY must be set and non-empty")
    return settings.SECRET_KEY


def derive_site_key(site_id: int) -> str:
    """Derive a deterministic per-site encryption key."""
    return hmac.new(
        _master_key().encode("utf-8"),
        str(site_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def encrypt_site_token(site_id: int, plaintext: str) -> str:
    """Encrypt a token for a specific site. Empty input stays empty."""
    if not plaintext:
        return ""
    return TokenEncryption(derive_site_key(site_id)).encrypt(plaintext)


def decrypt_site_token(site_id: int, ciphertext: str) -> str:
    """Decrypt a token for a specific site. Empty input stays empty."""
    if not ciphertext:
        return ""
    return TokenEncryption(derive_site_key(site_id)).decrypt(ciphertext)


def resolve_token(site_id: Optional[int], token: str) -> str:
    """Return a usable token.

    Fernet ciphertext (starts with ``gAAAA``) is decrypted with the per-site
    key. Plaintext (legacy rows, MCP test payloads) is returned as-is.
    """
    if not token:
        return ""
    if token.startswith("gAAAA"):
        if site_id is None:
            raise ValueError("Cannot decrypt site token without site_id")
        return decrypt_site_token(int(site_id), token)
    return token


def mask_token(token: str) -> str:
    """Mask a secret, revealing only the last 4 characters."""
    if not token:
        return ""
    return "****" + token[-4:]
