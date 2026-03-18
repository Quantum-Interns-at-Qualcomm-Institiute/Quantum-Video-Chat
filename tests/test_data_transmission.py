"""
Unit tests for the data-transmission pipeline primitives.

These tests verify encryption round-trips, key-index framing, and the
BroadcastFlaskNamespace relay logic — all of which live in shared/ and
do not depend on the middleware architecture.
"""
import pytest
from unittest.mock import MagicMock, patch

from shared.encryption import AESEncryption, DebugEncryption


# ---------------------------------------------------------------------------
# 1. Encryption round-trip
# ---------------------------------------------------------------------------

class TestEncryptionRoundTrip:
    """Verify that encrypt → decrypt recovers the original data."""

    def test_aes_round_trip(self):
        enc = AESEncryption()
        key = b'\xab' * 16
        plaintext = b'hello world, this is test data!!'
        ciphertext = enc.encrypt(plaintext, key)
        assert ciphertext != plaintext
        assert enc.decrypt(ciphertext, key) == plaintext

    def test_aes_different_keys_fail(self):
        enc = AESEncryption()
        key_a = b'\xab' * 16
        key_b = b'\xcd' * 16
        plaintext = b'some secret video frame bytes!!'
        ciphertext = enc.encrypt(plaintext, key_a)
        with pytest.raises(Exception):
            enc.decrypt(ciphertext, key_b)

    def test_debug_encryption_is_passthrough(self):
        enc = DebugEncryption()
        data = b'raw frame data here'
        assert enc.encrypt(data, b'ignored') == data
        assert enc.decrypt(data, b'ignored') == data

    def test_aes_handles_large_payload(self):
        """Simulate a realistic frame-sized payload (~50 KiB)."""
        enc = AESEncryption()
        key = b'\x42' * 16
        payload = bytes(range(256)) * 200  # 51200 bytes
        ct = enc.encrypt(payload, key)
        assert enc.decrypt(ct, key) == payload


# ---------------------------------------------------------------------------
# 2. Key-index framing
# ---------------------------------------------------------------------------

class TestKeyIndexFraming:
    """The protocol prepends a 4-byte big-endian key index to every message."""

    def test_encode_key_index(self):
        key_idx = 7
        header = key_idx.to_bytes(4, 'big')
        assert len(header) == 4
        assert int.from_bytes(header, 'big') == 7

    def test_round_trip_index(self):
        for idx in (0, 1, 255, 65535, 2**31 - 1):
            header = idx.to_bytes(4, 'big')
            assert int.from_bytes(header, 'big') == idx

    def test_payload_preserved_after_header(self):
        key_idx = 42
        payload = b'encrypted_data_here'
        msg = key_idx.to_bytes(4, 'big') + payload
        assert msg[4:] == payload
        assert int.from_bytes(msg[:4], 'big') == 42


# ---------------------------------------------------------------------------
# 3. BroadcastFlaskNamespace
# ---------------------------------------------------------------------------

class TestBroadcastFlaskNamespace:
    """The server-side namespace relays messages to everyone except the sender."""

    def test_relay_with_include_self_false(self):
        from shared.av.namespaces import BroadcastFlaskNamespace

        cls_stub = MagicMock()
        ns = BroadcastFlaskNamespace('/video', cls_stub)

        with patch('shared.av.namespaces.send') as mock_send:
            ns.on_message(('userA',), b'encrypted_frame')
            mock_send.assert_called_once_with(
                (('userA',), b'encrypted_frame'),
                broadcast=True,
                include_self=False,
            )

    def test_multiple_messages_relayed(self):
        from shared.av.namespaces import BroadcastFlaskNamespace

        cls_stub = MagicMock()
        ns = BroadcastFlaskNamespace('/video', cls_stub)

        with patch('shared.av.namespaces.send') as mock_send:
            for uid in ('userA', 'userB', 'userC'):
                ns.on_message((uid,), b'data')
            assert mock_send.call_count == 3
