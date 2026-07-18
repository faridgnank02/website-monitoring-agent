from core.security.encryption import TokenEncryption


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
    try:
        enc2.decrypt(ciphertext)
        assert False, "should have failed"
    except Exception:
        pass
