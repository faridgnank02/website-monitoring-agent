import pytest
from unittest.mock import patch

from core.security.site_encryption import (
    encrypt_site_token,
    decrypt_site_token,
    mask_token,
    resolve_token,
    derive_site_key,
)


MASTER = "test-master-secret-key"


@patch("config.settings.SECRET_KEY", MASTER)
def test_roundtrip_encrypt_decrypt():
    ciphertext = encrypt_site_token(1, "xoxb-slack-token")
    assert ciphertext != "xoxb-slack-token"
    assert decrypt_site_token(1, ciphertext) == "xoxb-slack-token"


@patch("config.settings.SECRET_KEY", MASTER)
def test_different_sites_cannot_cross_decrypt():
    ct_a = encrypt_site_token(1, "token-for-site-1")
    with pytest.raises(ValueError):
        decrypt_site_token(2, ct_a)


@patch("config.settings.SECRET_KEY", MASTER)
def test_derive_site_key_is_deterministic_and_site_specific():
    k1a = derive_site_key(1)
    k1b = derive_site_key(1)
    k2 = derive_site_key(2)
    assert k1a == k1b
    assert k1a != k2


@patch("config.settings.SECRET_KEY", MASTER)
def test_mask_token_shows_last_four():
    assert mask_token("abcdef1234") == "****1234"
    assert mask_token("") == ""
    assert mask_token("short") == "****hort"


@patch("config.settings.SECRET_KEY", MASTER)
def test_resolve_token_handles_plaintext_and_ciphertext():
    assert resolve_token(None, "http://plaintext") == "http://plaintext"
    ct = encrypt_site_token(1, "secret-value")
    assert resolve_token(1, ct) == "secret-value"
    assert resolve_token(1, "") == ""


@patch("config.settings.SECRET_KEY", MASTER)
def test_empty_plaintext_roundtrip_is_empty():
    assert encrypt_site_token(1, "") == ""
    assert decrypt_site_token(1, "") == ""
