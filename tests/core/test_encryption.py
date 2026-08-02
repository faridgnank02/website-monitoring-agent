import pytest
from unittest.mock import patch

from core.security.encryption import TokenEncryption, get_encryptor


def test_encrypt_decrypt_roundtrip():
    enc = TokenEncryption("test-secret-key-32bytes-long!!")
    ciphertext = enc.encrypt("my-slack-token")
    assert ciphertext != "my-slack-token"
    plaintext = enc.decrypt(ciphertext)
    assert plaintext == "my-slack-token"


def test_different_key_fails():
    enc1 = TokenEncryption("test-secret-key-32bytes-long!!")
    enc2 = TokenEncryption("different-key-32bytes-long!!")
    ciphertext = enc1.encrypt("my-token")
    with pytest.raises(ValueError, match="Invalid token or wrong encryption key"):
        enc2.decrypt(ciphertext)


def test_empty_secret_key_raises_value_error():
    with pytest.raises(ValueError, match="secret key cannot be empty or whitespace"):
        TokenEncryption("")


def test_get_encryptor_raises_when_secret_key_missing():
    with patch('config.settings.SECRET_KEY', ""):
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            get_encryptor()


def test_get_encryptor_returns_instance_when_secret_key_set():
    with patch('config.settings.SECRET_KEY', "valid-secret-key"):
        enc = get_encryptor()
        assert isinstance(enc, TokenEncryption)
