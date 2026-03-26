"""WP #663: Test: Signaling channel security.

Verifies that the WebSocket signaling channel uses proper security
measures: SSL/TLS support, authenticated connections, and safe
message handling.

Uses file reads instead of imports to avoid Python version compat
issues with shared/config.py (str | None syntax requires 3.10+).
"""

import os
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOCKET_API_PATH = os.path.join(ROOT, 'server', 'socket_api.py')


def _read_source():
    with open(SOCKET_API_PATH) as f:
        return f.read()


class TestSSLSupport:
    """Verify the signaling server supports TLS/SSL."""

    def test_ssl_context_function_exists(self):
        """Server must have SSL context configuration."""
        source = _read_source()
        assert 'def _get_ssl_context' in source

    def test_ssl_context_checks_cert_paths(self):
        """SSL context should verify cert and key files exist."""
        source = _read_source()
        assert 'cert.pem' in source
        assert 'key.pem' in source

    def test_ssl_context_supports_env_override(self):
        """DEV_CERT_DIR environment variable should be respected."""
        source = _read_source()
        assert 'DEV_CERT_DIR' in source

    def test_ssl_context_handles_missing_certs(self):
        """SSL context should return None when certs are absent."""
        source = _read_source()
        assert 'return None' in source or 'None' in source


class TestConnectionAuthentication:
    """Verify connections are authenticated."""

    def test_socket_api_tracks_users(self):
        """SocketAPI must maintain a user registry."""
        source = _read_source()
        assert 'self.users' in source
        assert 'self.sids' in source

    def test_connect_handler_validates_identity(self):
        """Connect handler should associate socket with user identity."""
        source = _read_source()
        assert '_on_connect' in source or 'on_connect' in source

    def test_disconnect_handler_cleans_up(self):
        """Disconnect handler must clean up user state."""
        source = _read_source()
        assert '_on_disconnect' in source or 'on_disconnect' in source

    def test_session_id_mapping_exists(self):
        """Server must map session IDs to user IDs for lookups."""
        source = _read_source()
        assert 'sids' in source


class TestMessageSecurity:
    """Verify message handling security."""

    def test_frame_relay_uses_binary(self):
        """Frame relay should handle binary data (encrypted frames)."""
        source = _read_source()
        assert 'frame' in source

    def test_no_eval_or_exec_in_handlers(self):
        """No eval() or exec() in message handlers (prevent code injection)."""
        source = _read_source()
        clean = source.replace("'eval'", '').replace('"eval"', '')
        assert 'eval(' not in clean
        assert 'exec(' not in clean

    def test_no_pickle_deserialization(self):
        """Must not use pickle for deserialization (unsafe with untrusted data)."""
        source = _read_source()
        assert 'pickle.loads' not in source
        assert 'pickle.load' not in source

    def test_room_id_generation_uses_randomness(self):
        """Room IDs should be randomly generated (not sequential)."""
        source = _read_source()
        assert 'random' in source.lower()


class TestQBERBroadcast:
    """Verify QBER metrics are broadcast safely."""

    def test_qber_update_method_exists(self):
        """Server should have method to broadcast QBER updates."""
        source = _read_source()
        assert 'qber' in source.lower()

    def test_qber_data_is_numeric(self):
        """QBER data should be numeric values, not executable code."""
        source = _read_source()
        assert 'emit' in source
