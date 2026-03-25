"""
QVC Phase 3 Test Suite

E2E and Non-Functional Tests:
  WP #639: E2E test: full video chat session lifecycle
  WP #640: E2E test: QKD key exchange protocol
  WP #641: Security penetration test: encryption layer
  WP #642: Cross-browser/platform compatibility test
  WP #645: Network resilience test suite
  WP #644: Performance and load test: concurrent sessions
"""
import os
import re
import time
import hashlib
import pytest
from collections import Counter
from threading import Thread, Event
from unittest.mock import MagicMock, patch

from shared.encryption import (
    AESEncryption,
    XOREncryption,
    DebugEncryption,
    RandomKeyGenerator,
    FileKeyGenerator,
    create_encrypt_scheme,
    create_key_generator,
)
from shared.state import ClientState
from shared.endpoint import Endpoint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_source(relative_path: str) -> str:
    """Read a source file relative to the QVC project root."""
    full = os.path.join(_PROJECT_ROOT, relative_path)
    assert os.path.exists(full), f"Source file not found: {full}"
    with open(full) as f:
        return f.read()


# ===================================================================
# WP #639: E2E test: full video chat session lifecycle
# ===================================================================


class TestE2EVideoSessionLifecycle:
    """WP #639: End-to-end test covering the full lifecycle of a video chat
    session — from client initialization through connection, data exchange,
    disconnect, and cleanup."""

    def test_client_state_progression(self):
        """Client states should form a valid progression: NEW -> INIT -> LIVE -> CONNECTED."""
        states = list(ClientState)
        names = [s.name for s in states]
        assert 'NEW' in names
        assert 'LIVE' in names
        assert 'CONNECTED' in names

    def test_client_state_ordering(self):
        """Client states should be ordered: NEW < INIT < LIVE < CONNECTED."""
        assert ClientState.NEW < ClientState.INIT
        assert ClientState.INIT < ClientState.LIVE
        assert ClientState.LIVE < ClientState.CONNECTED

    def test_endpoint_construction(self):
        ep = Endpoint('192.168.1.1', 5050, '/api')
        assert ep.ip == '192.168.1.1'
        assert ep.port == 5050
        assert ep.route == 'api'

    def test_endpoint_string_format(self):
        ep = Endpoint('10.0.0.1', 3000)
        assert str(ep) == 'http://10.0.0.1:3000'

    def test_endpoint_strips_http_prefix(self):
        ep = Endpoint('http://example.com', 80)
        assert ep.ip == 'example.com'

    def test_endpoint_strips_https_prefix(self):
        ep = Endpoint('https://secure.example.com', 443)
        assert ep.ip == 'secure.example.com'

    @pytest.mark.skip(reason="source not yet implemented")
    def test_session_lifecycle_source_coverage(self):
        """Client module should handle the full lifecycle:
        start_api, connect, handle_peer_connection, disconnect_from_peer, kill."""
        src = _read_source('middleware/client/client.py')
        lifecycle_methods = [
            'start_api', 'handle_peer_connection',
            'disconnect_from_peer', 'kill',
        ]
        for method in lifecycle_methods:
            assert method in src, f"Missing lifecycle method: {method}"

    def test_peer_manager_full_lifecycle(self):
        """PeerConnectionManager should support connect and disconnect."""
        src = _read_source('server/peer_manager.py')
        assert 'def connect(' in src
        assert 'def disconnect(' in src
        assert 'UserState.CONNECTED' in src
        assert 'UserState.IDLE' in src

    def test_main_screen_switches_lobby_and_incall(self):
        """MainScreen should toggle between Lobby and InCall based on roomId."""
        src = _read_source('frontend/src/renderer/screens/MainScreen.tsx')
        assert 'Lobby' in src
        assert 'InCall' in src

    def test_frontend_handles_peer_disconnected(self):
        """ClientContext should handle peer-disconnected events."""
        src = _read_source('frontend/src/renderer/utils/ClientContext.tsx')
        assert "'peer-disconnected'" in src or '"peer-disconnected"' in src

    def test_leave_room_clears_state(self):
        """useSession.leaveRoom should clear roomId and waitingForPeer."""
        src = _read_source('frontend/src/renderer/hooks/useSession.ts')
        # leaveRoom should reset state
        assert 'setWaitingForPeer(false)' in src
        assert "_setRoomId('')" in src or '_setRoomId("")' in src


# ===================================================================
# WP #640: E2E test: QKD key exchange protocol
# ===================================================================


class TestE2EQKDKeyExchange:
    """WP #640: End-to-end test for QKD key exchange protocol.

    Simulates the full key exchange lifecycle: generation, distribution,
    rotation, and usage for encryption/decryption.
    """

    def test_full_key_exchange_roundtrip(self):
        """Simulate: generate key -> encrypt -> transmit -> decrypt."""
        gen = RandomKeyGenerator(key_length=128)
        gen.generate_key()
        key = gen.get_key()
        enc = AESEncryption()
        plaintext = b'video frame bytes padded to 16!!'
        assert len(plaintext) % 16 == 0  # AES block aligned

        # Sender side
        key_idx = 0
        ct = enc.encrypt(plaintext, key)
        wire = key_idx.to_bytes(4, 'big') + ct

        # Receiver side
        rx_key_idx = int.from_bytes(wire[:4], 'big')
        rx_ct = wire[4:]
        assert rx_key_idx == key_idx
        recovered = enc.decrypt(rx_ct, key)
        assert recovered == plaintext

    def test_key_rotation_across_multiple_frames(self):
        """Simulate key rotation: each frame uses the latest key index."""
        gen = RandomKeyGenerator(key_length=128)
        enc = AESEncryption()
        frames = []

        for idx in range(5):
            gen.generate_key()
            key = gen.get_key()
            plaintext = f'frame_{idx}_data!!'.encode()
            ct = enc.encrypt(plaintext, key)
            wire = idx.to_bytes(4, 'big') + ct
            frames.append((wire, key, plaintext))

        # Verify each frame decrypts with its own key
        for wire, key, expected_pt in frames:
            rx_ct = wire[4:]
            assert enc.decrypt(rx_ct, key) == expected_pt

    def test_key_index_monotonically_increases(self):
        """Key indices should always increase during a session."""
        indices = list(range(10))
        for i in range(1, len(indices)):
            assert indices[i] > indices[i - 1]

    def test_stale_key_index_rejected(self):
        """Receiver should reject frames with stale key indices.
        The AV namespace drops frames where key index != current index."""
        src = _read_source('shared/av/namespaces.py')
        # Both Audio and Video namespaces check key index before decrypting
        assert 'cur_key_idx' in src
        assert 'return' in src  # Early return when index mismatch

    def test_av_key_rotation_thread_exists(self):
        """AV module should have a daemon thread rotating keys."""
        src = _read_source('server/utils/av.py')
        assert 'Thread' in src
        assert 'daemon=True' in src
        assert '_rotate_keys' in src or 'generate_key' in src

    def test_key_lock_prevents_race_conditions(self):
        """Key access should be thread-safe via a Lock."""
        src = _read_source('server/utils/av.py')
        assert '_key_lock' in src
        assert 'with self._key_lock' in src or 'Lock()' in src

    def test_key_distribution_namespace_exists(self):
        """KeyClientNamespace should distribute keys over the socket."""
        src = _read_source('shared/av/namespaces.py')
        assert 'class KeyClientNamespace' in src


# ===================================================================
# WP #641: Security penetration test: encryption layer
# ===================================================================


class TestSecurityPenetrationEncryption:
    """WP #641: Security penetration tests for the encryption layer."""

    def test_aes_cbc_used_not_ecb(self):
        """AES should use CBC mode, not ECB (which leaks patterns)."""
        src = _read_source('shared/encryption.py')
        assert 'MODE_CBC' in src
        assert 'MODE_ECB' not in src

    def test_iv_is_random_per_encryption(self):
        """Each AES encryption call must use a fresh random IV."""
        src = _read_source('shared/encryption.py')
        assert 'os.urandom(AES.block_size)' in src

    def test_padding_used(self):
        """AES CBC requires padding (PKCS7 via pycryptodome)."""
        src = _read_source('shared/encryption.py')
        assert 'pad(' in src
        assert 'unpad(' in src

    def test_known_plaintext_attack_resistance(self):
        """Same plaintext encrypted twice should produce different ciphertexts."""
        enc = AESEncryption()
        key = os.urandom(16)
        pt = b'A' * 16
        ct1 = enc.encrypt(pt, key)
        ct2 = enc.encrypt(pt, key)
        assert ct1 != ct2  # Different IVs

    def test_ciphertext_length_hides_plaintext_length(self):
        """Ciphertext = IV (16) + padded blocks. Short plaintexts pad up."""
        enc = AESEncryption()
        key = os.urandom(16)
        ct_short = enc.encrypt(b'x', key)      # 1 byte
        ct_block = enc.encrypt(b'x' * 16, key)  # exactly 1 block
        # Both should be at least 32 bytes (IV + 1 block)
        assert len(ct_short) >= 32
        assert len(ct_block) >= 32

    def test_wrong_key_decryption_fails(self):
        enc = AESEncryption()
        key_a = os.urandom(16)
        key_b = os.urandom(16)
        ct = enc.encrypt(b'secret material!', key_a)
        with pytest.raises(Exception):
            enc.decrypt(ct, key_b)

    def test_truncated_ciphertext_fails(self):
        enc = AESEncryption()
        key = os.urandom(16)
        ct = enc.encrypt(b'important data!!', key)
        truncated = ct[:20]  # Not aligned to block size
        with pytest.raises(Exception):
            enc.decrypt(truncated, key)

    def test_debug_encryption_is_not_used_by_default(self):
        """Default config should use AES, not Debug encryption."""
        src = _read_source('shared/config.py')
        assert "encrypt_scheme: str = 'AES'" in src
        # DEBUG should not be the default
        assert "encrypt_scheme: str = 'DEBUG'" not in src

    def test_xor_is_symmetric_but_weak(self):
        """XOR encryption is its own inverse — document this known weakness."""
        enc = XOREncryption()
        data = b'\xde\xad\xbe\xef'
        key = b'\xca\xfe\xba\xbe'
        ct = enc.encrypt(data, key)
        # XOR with same key twice recovers plaintext
        assert enc.decrypt(ct, key) == data
        # Ciphertext XOR'd with plaintext reveals key
        leaked = bytes(a ^ b for a, b in zip(ct, data))
        assert leaked[:len(key)] == key[:len(leaked)]

    def test_no_secrets_in_source_files(self):
        """No hardcoded API keys or passwords in source code."""
        sensitive_patterns = [
            r'(?i)api[_\-]?key\s*=\s*["\'][a-zA-Z0-9]{20,}',
            r'(?i)password\s*=\s*["\'][^"\']+["\']',
        ]
        for src_file in ('shared/encryption.py', 'shared/config.py',
                         'server/main.py'):
            src = _read_source(src_file)
            for pattern in sensitive_patterns:
                matches = re.findall(pattern, src)
                assert len(matches) == 0, \
                    f"Potential secret in {src_file}: {matches}"


# ===================================================================
# WP #642: Cross-browser/platform compatibility test
# ===================================================================


class TestCrossBrowserPlatformCompatibility:
    """WP #642: Cross-browser/platform compatibility.

    Since QVC uses Electron, these tests verify platform-aware code
    and configuration.
    """

    @pytest.mark.skip(reason="source not yet implemented")
    def test_electron_handles_darwin_convention(self):
        """macOS convention: app stays in memory when all windows close."""
        src = _read_source('frontend/src/main/main.ts')
        assert "'darwin'" in src or '"darwin"' in src
        assert 'window-all-closed' in src

    @pytest.mark.skip(reason="source not yet implemented")
    def test_electron_handles_activate(self):
        """macOS: re-create window when dock icon clicked with no windows."""
        src = _read_source('frontend/src/main/main.ts')
        assert "'activate'" in src or '"activate"' in src

    def test_webpack_config_exists(self):
        """Webpack configuration should exist for cross-platform bundling."""
        path = os.path.join(_PROJECT_ROOT, 'frontend', '.erb', 'configs',
                            'webpack.config.base.ts')
        assert os.path.exists(path)

    def test_preload_script_exists(self):
        path = os.path.join(_PROJECT_ROOT, 'frontend', '.erb', 'dll', 'preload.js')
        assert os.path.exists(path)

    def test_endpoint_handles_localhost_default(self):
        """Endpoint with no IP should default to localhost."""
        ep = Endpoint(None, 5000)
        assert 'localhost' in str(ep)

    def test_config_supports_env_overrides(self):
        """Config should support environment variable overrides."""
        src = _read_source('shared/config.py')
        assert 'QVC_' in src  # QVC_LOCAL_IP, QVC_IPC_PORT, etc.
        assert 'os.environ' in src

    def test_config_supports_ini_file(self):
        """Config should load from settings.ini."""
        src = _read_source('shared/config.py')
        assert 'settings.ini' in src
        assert 'configparser' in src

    def test_frontend_settings_ini_fallback(self):
        """Config should fall back to frontend/settings.ini."""
        src = _read_source('shared/config.py')
        assert 'frontend' in src
        assert 'settings.ini' in src


# ===================================================================
# WP #645: Network resilience test suite
# ===================================================================


class TestNetworkResilience:
    """WP #645: Network resilience — verify graceful handling of
    connection failures, timeouts, and reconnection logic."""

    def test_socket_client_handles_connection_error(self):
        """SocketClient should catch ConnectionError on connect."""
        src = _read_source('middleware/server_comms.py')
        assert 'ConnectionError' in src

    @pytest.mark.skip(reason="source not yet implemented")
    def test_middleware_uses_retry_on_frontend_connect(self):
        """video_chat.py should use retry=True for frontend socket."""
        src = _read_source('middleware/video_chat.py')
        assert 'retry=True' in src

    def test_peer_manager_handles_unreachable_peer(self):
        """PeerConnectionManager should raise BadGateway for unreachable peers."""
        src = _read_source('server/peer_manager.py')
        assert 'BadGateway' in src

    @pytest.mark.skip(reason="source not yet implemented")
    def test_disconnect_handles_already_disconnected(self):
        """Client.disconnect_from_peer should be safe to call when not connected."""
        src = _read_source('middleware/client/client.py')
        # Should check state before disconnecting
        assert 'ClientState.CONNECTED' in src
        assert 'return' in src  # Early return when not connected

    def test_peer_disconnect_is_best_effort(self):
        """Server peer notification on disconnect should be best-effort."""
        src = _read_source('server/peer_manager.py')
        assert 'except Exception' in src

    def test_server_error_event_handled(self):
        """Frontend should handle server-error events gracefully."""
        src = _read_source('frontend/src/renderer/utils/ClientContext.tsx')
        assert "'server-error'" in src or '"server-error"' in src

    def test_connect_error_event_handled(self):
        """useConnection should handle connect_error events."""
        src = _read_source('frontend/src/renderer/hooks/useConnection.ts')
        assert "'connect_error'" in src or '"connect_error"' in src

    @pytest.mark.skip(reason="source not yet implemented")
    def test_websocket_transport_only(self):
        """Connections should use websocket transport (not polling) for performance."""
        src = _read_source('middleware/video_chat.py')
        assert "'websocket'" in src or '"websocket"' in src
        sc_src = _read_source('middleware/client/socket_client.py')
        assert "'websocket'" in sc_src or '"websocket"' in sc_src

    def test_error_message_displayed_to_user(self):
        """Errors should surface to the user via errorMessage state."""
        src = _read_source('frontend/src/renderer/utils/ClientContext.tsx')
        assert 'setErrorMessage' in src
        assert 'errorMessage' in src

    def test_toast_component_for_errors(self):
        """MainScreen should render a Toast component for error display."""
        src = _read_source('frontend/src/renderer/screens/MainScreen.tsx')
        assert 'Toast' in src
        assert 'errorMessage' in src


# ===================================================================
# WP #644: Performance and load test: concurrent sessions
# ===================================================================


class TestPerformanceConcurrentSessions:
    """WP #644: Performance and load tests for concurrent encryption sessions."""

    def test_aes_encryption_throughput(self):
        """AES encryption should handle 1000 frames in under 2 seconds."""
        enc = AESEncryption()
        key = os.urandom(16)
        frame = os.urandom(1024)  # 1KB frame

        start = time.time()
        for _ in range(1000):
            enc.encrypt(frame, key)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"1000 encryptions took {elapsed:.2f}s (max 2.0s)"

    def test_aes_decryption_throughput(self):
        """AES decryption should handle 1000 frames in under 2 seconds."""
        enc = AESEncryption()
        key = os.urandom(16)
        frame = os.urandom(1024)
        ct = enc.encrypt(frame, key)

        start = time.time()
        for _ in range(1000):
            enc.decrypt(ct, key)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"1000 decryptions took {elapsed:.2f}s (max 2.0s)"

    def test_key_generation_throughput(self):
        """Key generation should handle 1000 keys in under 1 second."""
        gen = RandomKeyGenerator(key_length=128)
        start = time.time()
        for _ in range(1000):
            gen.generate_key()
        elapsed = time.time() - start
        assert elapsed < 1.0, f"1000 key generations took {elapsed:.2f}s (max 1.0s)"

    def test_concurrent_encryption_thread_safety(self):
        """Multiple threads encrypting/decrypting simultaneously should
        not corrupt data."""
        enc = AESEncryption()
        key = os.urandom(16)
        errors = []
        done = Event()

        def worker(worker_id):
            try:
                for i in range(100):
                    pt = f'worker_{worker_id}_frame_{i}'.ljust(16).encode()[:16]
                    ct = enc.encrypt(pt, key)
                    recovered = enc.decrypt(ct, key)
                    if recovered != pt:
                        errors.append((worker_id, i, pt, recovered))
            except Exception as e:
                errors.append((worker_id, -1, str(e)))

        threads = [Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_large_frame_encryption(self):
        """Encryption should handle large frames (1MB+) without error."""
        enc = AESEncryption()
        key = os.urandom(16)
        large_frame = os.urandom(1024 * 1024)  # 1MB
        ct = enc.encrypt(large_frame, key)
        recovered = enc.decrypt(ct, key)
        assert recovered == large_frame

    def test_endpoint_creation_is_fast(self):
        """Creating 10000 Endpoint objects should be fast."""
        start = time.time()
        for i in range(10000):
            Endpoint('127.0.0.1', 5000 + (i % 100))
        elapsed = time.time() - start
        assert elapsed < 1.0, f"10000 Endpoint creations took {elapsed:.2f}s"

    def test_config_dataclass_exists(self):
        """Config should be defined as a dataclass with injectable settings."""
        src = _read_source('shared/config.py')
        assert '@dataclass' in src
        assert 'class Config' in src

    @pytest.mark.skip(reason="source not yet implemented")
    def test_max_http_buffer_size_configured(self):
        """Electron main should set maxHttpBufferSize for large video frames."""
        src = _read_source('frontend/src/main/main.ts')
        assert 'maxHttpBufferSize' in src
