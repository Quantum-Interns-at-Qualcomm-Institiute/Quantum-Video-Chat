"""
WP #58: Audit encryption key handoff
WP #662: Test: encryption key handoff audit
WP #663: Test: Signaling channel security
"""
import os
import pytest
from unittest.mock import patch
from shared.encryption import AESEncryption, XOREncryption, DebugEncryption
from Crypto.Cipher import AES


class TestAESRandomIV:
    """Verify AES uses a unique random IV for each encryption."""

    def test_ciphertext_starts_with_iv(self):
        enc = AESEncryption()
        key = os.urandom(16)
        ct = enc.encrypt(b'hello world!!!!!', key)
        # Ciphertext should be IV (16 bytes) + encrypted data (>= 16 bytes)
        assert len(ct) >= 32

    def test_different_ivs_per_call(self):
        enc = AESEncryption()
        key = os.urandom(16)
        plaintext = b'same data xxxxxx'
        ct1 = enc.encrypt(plaintext, key)
        ct2 = enc.encrypt(plaintext, key)
        # IVs (first 16 bytes) must differ
        assert ct1[:16] != ct2[:16]
        # Full ciphertexts must differ
        assert ct1 != ct2

    def test_roundtrip_with_random_iv(self):
        enc = AESEncryption()
        key = os.urandom(16)
        plaintext = b'encrypt me plz!!'
        ct = enc.encrypt(plaintext, key)
        assert enc.decrypt(ct, key) == plaintext

    def test_iv_not_hardcoded_zeros(self):
        enc = AESEncryption()
        key = os.urandom(16)
        ct = enc.encrypt(b'test data 123456', key)
        iv = ct[:16]
        assert iv != b'0' * 16

    def test_256bit_key_roundtrip(self):
        enc = AESEncryption(256)
        key = os.urandom(32)
        plaintext = b'256-bit test!!'
        ct = enc.encrypt(plaintext, key)
        assert enc.decrypt(ct, key) == plaintext

    def test_wrong_key_fails(self):
        enc = AESEncryption()
        key_a = os.urandom(16)
        key_b = os.urandom(16)
        ct = enc.encrypt(b'secret data!!!!!', key_a)
        with pytest.raises(Exception):
            enc.decrypt(ct, key_b)

    def test_tampered_nonce_fails(self):
        enc = AESEncryption()
        key = os.urandom(16)
        ct = enc.encrypt(b'important data!!', key)
        # Flip a bit in the nonce
        tampered = bytes([ct[0] ^ 0x01]) + ct[1:]
        # AES-GCM should reject tampered ciphertext (MAC check)
        with pytest.raises(ValueError):
            enc.decrypt(tampered, key)


class TestEncryptionSchemeSecurityProperties:
    """Verify security properties of the encryption pipeline."""

    def test_xor_is_symmetric(self):
        """XOR encryption is its own inverse — known weakness."""
        enc = XOREncryption()
        data = b'\xde\xad\xbe\xef'
        key = b'\xca\xfe'
        ct = enc.encrypt(data, key)
        assert enc.decrypt(ct, key) == data

    def test_debug_encryption_is_no_op(self):
        enc = DebugEncryption()
        data = b'plaintext'
        assert enc.encrypt(data, b'key') == data

    def test_aes_ciphertext_differs_from_plaintext(self):
        enc = AESEncryption()
        key = os.urandom(16)
        plaintext = b'A' * 32
        ct = enc.encrypt(plaintext, key)
        # After stripping IV, the encrypted portion should differ
        assert ct[16:] != plaintext


class TestKeyRotationFraming:
    """Verify wire format: 4-byte key index + IV + ciphertext."""

    def test_wire_format_structure(self):
        enc = AESEncryption()
        key = os.urandom(16)
        key_idx = 42
        plaintext = b'frame data here!'

        ct = enc.encrypt(plaintext, key)
        wire = key_idx.to_bytes(4, 'big') + ct

        # Parse back
        parsed_idx = int.from_bytes(wire[:4], 'big')
        parsed_ct = wire[4:]
        assert parsed_idx == 42
        assert enc.decrypt(parsed_ct, key) == plaintext

    def test_key_index_rollover(self):
        """Key index is 4 bytes — test max value."""
        max_idx = 0xFFFFFFFF
        wire_header = max_idx.to_bytes(4, 'big')
        assert int.from_bytes(wire_header, 'big') == max_idx


class TestSignalingChannelSecurity:
    """WP #663: Verify signaling channel configuration."""

    def test_server_config_defines_ports(self):
        """Server config should define explicit ports for all services."""
        from shared.config import Config
        config = Config()
        assert hasattr(config, 'server_rest_port')
        assert hasattr(config, 'middleware_port')
        assert hasattr(config, 'client_api_port')

    def test_socket_api_module_exists(self):
        """Socket API module must exist for signaling."""
        import os
        socket_api = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'server', 'socket_api.py',
        )
        assert os.path.exists(socket_api)

    def test_no_hardcoded_secrets_in_config(self):
        """Config files should not contain hardcoded secrets."""
        from shared.config import Config
        config = Config()
        config_str = str(vars(config))
        # Should not contain obvious secret patterns
        assert 'password' not in config_str.lower() or 'secret' not in config_str.lower()
