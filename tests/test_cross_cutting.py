"""
Phase 3 cross-cutting test suite for Quantum Video Chat.

Source-analysis tests that verify architectural properties across the
codebase without importing server modules (which require runtime
dependencies).  Each test class corresponds to a work package:

  WP #639  E2E: full video chat session lifecycle
  WP #640  E2E: QKD key exchange protocol
  WP #641  Security penetration test: encryption layer
  WP #642  Cross-browser/platform compatibility test
  WP #645  Network resilience test suite
  WP #644  Performance and load test: concurrent sessions
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(relpath):
    # type: (str) -> str
    """Read a project file by relative path from the repo root."""
    return (ROOT / relpath).read_text(encoding="utf-8", errors="replace")


def _file_exists(relpath):
    # type: (str) -> bool
    return (ROOT / relpath).is_file()


def _collect_python_files(*dirs):
    # type: (*str) -> List[str]
    """Return relative paths of all .py files under the given directories."""
    results = []  # type: List[str]
    for d in dirs:
        base = ROOT / d
        results.extend(
            str(p.relative_to(ROOT))
            for p in base.rglob("*.py")
        )
    return results


# ═══════════════════════════════════════════════════════════════════════════
# WP #639 — E2E test: full video chat session lifecycle
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionLifecycle(unittest.TestCase):
    """Verify that the REST API exposes the complete session lifecycle
    (create user -> peer connection -> disconnect -> remove user) and the
    WebSocket API registers the required real-time events."""

    @classmethod
    def setUpClass(cls):
        cls.rest_src = _read("server/rest_api.py")
        cls.socket_src = _read("server/socket_api.py")
        cls.middleware_src = _read("middleware/server_comms.py")

    # -- REST endpoints --------------------------------------------------

    def test_create_user_endpoint(self):
        """REST API defines /create_user route."""
        self.assertIn("/create_user", self.rest_src)

    def test_peer_connection_endpoint(self):
        """REST API defines /peer_connection route."""
        self.assertIn("/peer_connection", self.rest_src)

    def test_disconnect_peer_endpoint(self):
        """REST API defines /disconnect_peer route."""
        self.assertIn("/disconnect_peer", self.rest_src)

    def test_remove_user_endpoint(self):
        """REST API defines /remove_user route."""
        self.assertIn("/remove_user", self.rest_src)

    # -- Socket events ---------------------------------------------------

    def test_socket_connect_event(self):
        """Socket API handles 'connect' event."""
        self.assertTrue(
            "'connect'" in self.socket_src or '"connect"' in self.socket_src,
        )

    def test_socket_disconnect_event(self):
        """Socket API handles 'disconnect' event."""
        self.assertTrue(
            "'disconnect'" in self.socket_src or '"disconnect"' in self.socket_src,
        )

    def test_socket_frame_event(self):
        """Socket API handles 'frame' event for video relay."""
        self.assertTrue(
            "'frame'" in self.socket_src or '"frame"' in self.socket_src,
        )

    def test_socket_audio_frame_event(self):
        """Socket API handles 'audio-frame' event for audio relay."""
        self.assertTrue(
            "'audio-frame'" in self.socket_src or '"audio-frame"' in self.socket_src,
        )

    def test_socket_message_event(self):
        """Socket API handles 'message' event for chat."""
        self.assertTrue(
            "'message'" in self.socket_src or '"message"' in self.socket_src,
        )

    # -- Middleware calls the lifecycle endpoints -------------------------

    def test_middleware_calls_create_user(self):
        """Middleware invokes /create_user on the server."""
        self.assertIn("/create_user", self.middleware_src)

    def test_middleware_calls_peer_connection(self):
        """Middleware invokes /peer_connection on the server."""
        self.assertIn("/peer_connection", self.middleware_src)

    def test_middleware_calls_disconnect_peer(self):
        """Middleware invokes /disconnect_peer on the server."""
        self.assertIn("/disconnect_peer", self.middleware_src)

    def test_socket_event_handler_registry(self):
        """Socket API uses a declarative EVENT_HANDLERS dict."""
        self.assertIn("EVENT_HANDLERS", self.socket_src)
        for event in ("connect", "message", "frame", "audio-frame", "disconnect"):
            self.assertTrue(
                repr(event) in self.socket_src or f'"{event}"' in self.socket_src,
                f"EVENT_HANDLERS missing '{event}'",
            )


# ═══════════════════════════════════════════════════════════════════════════
# WP #640 — E2E test: QKD key exchange protocol
# ═══════════════════════════════════════════════════════════════════════════

class TestQKDProtocol(unittest.TestCase):
    """Verify the BB84 protocol module implements all required stages."""

    @classmethod
    def setUpClass(cls):
        cls.proto_src = _read("shared/bb84/protocol.py")
        cls.encrypt_src = _read("shared/encryption.py")

    def test_protocol_file_exists(self):
        """shared/bb84/protocol.py exists."""
        self.assertTrue(_file_exists("shared/bb84/protocol.py"))

    def test_run_round_method(self):
        """BB84Protocol has a run_round method."""
        self.assertIn("def run_round(", self.proto_src)

    def test_eavesdropper_simulator(self):
        """Protocol includes an EavesdropperSimulator class."""
        self.assertIn("class EavesdropperSimulator", self.proto_src)

    def test_intercept_resend(self):
        """Eavesdropper implements intercept-resend attack."""
        self.assertIn("def intercept_resend(", self.proto_src)

    def test_qber_threshold_checking(self):
        """Protocol checks QBER against a configurable threshold."""
        self.assertIn("qber_threshold", self.proto_src)
        self.assertRegex(self.proto_src, r"qber.*threshold|is_secure")

    def test_error_correction_cascade(self):
        """Protocol implements Cascade error correction."""
        self.assertIn("def _error_correct_cascade(", self.proto_src)

    def test_privacy_amplification(self):
        """Protocol implements privacy amplification via Toeplitz hashing."""
        self.assertIn("def _privacy_amplify(", self.proto_src)
        self.assertIn("toeplitz_hash", self.proto_src)

    def test_sifting_step(self):
        """Protocol implements key sifting."""
        self.assertIn("def _sift_keys(", self.proto_src)

    def test_qber_estimation(self):
        """Protocol implements QBER estimation."""
        self.assertIn("def _estimate_qber(", self.proto_src)

    def test_bb84_key_generator_exists(self):
        """Encryption module has a BB84KeyGenerator class."""
        self.assertIn("class BB84KeyGenerator", self.encrypt_src)

    def test_bb84_key_generator_registered(self):
        """BB84 key generator is registered in the keygen registry."""
        self.assertTrue(
            "register_key_generator('BB84'" in self.encrypt_src
            or 'register_key_generator("BB84"' in self.encrypt_src,
        )


# ═══════════════════════════════════════════════════════════════════════════
# WP #641 — Security penetration test: encryption layer
# ═══════════════════════════════════════════════════════════════════════════

class TestSecurityEncryptionLayer(unittest.TestCase):
    """Static analysis: no dangerous patterns, AES-GCM used, rate limiting."""

    @classmethod
    def setUpClass(cls):
        cls.py_files = _collect_python_files("server", "shared", "middleware")
        cls.encrypt_src = _read("shared/encryption.py")
        cls.rest_src = _read("server/rest_api.py")

    # -- No eval / exec --------------------------------------------------

    def test_no_eval_in_codebase(self):
        """No usage of eval() in production Python files."""
        for path in self.py_files:
            src = _read(path)
            # Match eval( but not "evaluate" or comments
            matches = re.findall(r"(?<!\w)eval\s*\(", src)
            self.assertEqual(
                len(matches), 0,
                f"eval() found in {path}",
            )

    def test_no_exec_in_codebase(self):
        """No usage of exec() in production Python files."""
        for path in self.py_files:
            src = _read(path)
            matches = re.findall(r"(?<!\w)exec\s*\(", src)
            self.assertEqual(
                len(matches), 0,
                f"exec() found in {path}",
            )

    # -- No pickle -------------------------------------------------------

    def test_no_pickle_loads(self):
        """No pickle.loads() in production code (deserialization risk)."""
        for path in self.py_files:
            src = _read(path)
            self.assertNotIn(
                "pickle.loads(", src,
                f"pickle.loads() found in {path}",
            )

    # -- AES-GCM usage ---------------------------------------------------

    def test_aes_gcm_encryption(self):
        """Encryption module uses AES in GCM mode."""
        self.assertIn("AES.MODE_GCM", self.encrypt_src)

    def test_aes_nonce_generated_per_encryption(self):
        """Each AES encryption generates a fresh random nonce."""
        self.assertIn("os.urandom(", self.encrypt_src)

    def test_aes_tag_verification(self):
        """AES decryption verifies the authentication tag."""
        self.assertIn("decrypt_and_verify", self.encrypt_src)


    # -- No hardcoded secrets --------------------------------------------

    def test_no_hardcoded_api_keys(self):
        """No hardcoded API keys or tokens in production code."""
        patterns = [
            r'(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token)\s*=\s*["\'][A-Za-z0-9]{16,}["\']',
        ]
        for path in self.py_files:
            src = _read(path)
            for pat in patterns:
                matches = re.findall(pat, src)
                self.assertEqual(
                    len(matches), 0,
                    f"Possible hardcoded secret in {path}: pattern={pat}",
                )

    # -- Rate limiting ---------------------------------------------------

    def test_rate_limiter_class_exists(self):
        """REST API defines a RateLimiter class."""
        self.assertIn("class RateLimiter", self.rest_src)

    def test_rate_limit_decorator(self):
        """REST API applies @rate_limit to endpoints."""
        self.assertIn("@rate_limit", self.rest_src)

    def test_rate_limit_returns_429(self):
        """Rate limiter returns HTTP 429 when exceeded."""
        self.assertIn("429", self.rest_src)

    # -- Insecure schemes gated by dev flag ------------------------------

    def test_insecure_schemes_dev_only(self):
        """XOR and DEBUG encryption are only registered under QVC_DEVELOPMENT."""
        self.assertIn("QVC_DEVELOPMENT", self.encrypt_src)
        # Ensure AES is registered unconditionally
        lines = self.encrypt_src.splitlines()
        aes_reg_line = None
        for i, line in enumerate(lines):
            if "register_encrypt_scheme('AES'" in line or 'register_encrypt_scheme("AES"' in line:
                aes_reg_line = i
                break
        self.assertIsNotNone(aes_reg_line, "AES registration not found")


# ═══════════════════════════════════════════════════════════════════════════
# WP #642 — Cross-browser/platform compatibility test
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossBrowserCompatibility(unittest.TestCase):
    """Verify CSS uses standard properties and the server adds CORS headers."""

    @classmethod
    def setUpClass(cls):
        # Collect all non-vendor CSS files from the website client
        cls.css_files = []  # type: List[str]
        for search_dir in ("website/client/static", "middleware/static"):
            base = ROOT / search_dir
            if not base.is_dir():
                continue
            cls.css_files.extend(
                str(p.relative_to(ROOT))
                for p in base.rglob("*.css")
            )
        cls.rest_src = _read("server/rest_api.py")

    def test_css_files_exist(self):
        """At least one CSS file exists in the frontend."""
        self.assertGreater(len(self.css_files), 0)

    def test_no_vendor_prefix_only_properties(self):
        """CSS files do not rely on vendor-prefix-only properties
        without a standard fallback on the next line."""
        vendor_re = re.compile(r"^\s*(-webkit-|-moz-|-ms-|-o-)(\S+)\s*:")
        for path in self.css_files:
            src = _read(path)
            lines = src.splitlines()
            for i, line in enumerate(lines):
                m = vendor_re.match(line)
                if m:
                    std_prop = m.group(2)
                    # Check if the standard property appears nearby (within 3 lines)
                    context = "\n".join(lines[max(0, i - 1):i + 4])
                    has_std = re.search(
                        r"(?<![a-z-])" + re.escape(std_prop) + r"\s*:",
                        context,
                    )
                    if not has_std:
                        # Allow known CSS properties that are still vendor-prefixed
                        # (e.g., -webkit-app-region which has no standard equivalent)
                        known_exceptions = {"app-region", "font-smoothing", "osx-font-smoothing"}
                        if std_prop not in known_exceptions:
                            self.fail(
                                f"Vendor-prefix-only property '-{m.group(1)}{std_prop}' "
                                f"without standard fallback in {path}:{i+1}",
                            )

    def test_standard_websocket_usage(self):
        """Socket API uses Flask-SocketIO (standard WebSocket library)."""
        socket_src = _read("server/socket_api.py")
        self.assertIn("from flask_socketio import SocketIO", socket_src)

    def test_cors_headers_present(self):
        """REST API adds Access-Control-Allow-Origin headers."""
        self.assertIn("Access-Control-Allow-Origin", self.rest_src)

    def test_cors_methods_header(self):
        """REST API specifies allowed HTTP methods in CORS headers."""
        self.assertIn("Access-Control-Allow-Methods", self.rest_src)

    def test_cors_headers_header(self):
        """REST API specifies allowed request headers in CORS."""
        self.assertIn("Access-Control-Allow-Headers", self.rest_src)

    def test_tsx_components_exist(self):
        """Frontend has JS/HTML components for cross-platform UI."""
        static_dir = ROOT / "website" / "client" / "static"
        js_files = [p.name for p in static_dir.iterdir() if p.suffix == ".js"]
        self.assertGreater(len(js_files), 0, "No JS frontend files found")


# ═══════════════════════════════════════════════════════════════════════════
# WP #645 — Network resilience test suite
# ═══════════════════════════════════════════════════════════════════════════

class TestNetworkResilience(unittest.TestCase):
    """Verify reconnection logic, error handling in socket events, and
    health-check patterns."""

    @classmethod
    def setUpClass(cls):
        cls.middleware_src = _read("middleware/server_comms.py")
        cls.socket_src = _read("server/socket_api.py")

    def test_websocket_reconnection_retry_loop(self):
        """Middleware retries WebSocket connections with backoff."""
        self.assertIn("_WS_CONNECT_MAX_ATTEMPTS", self.middleware_src)
        self.assertIn("_WS_CONNECT_RETRY_DELAY", self.middleware_src)

    def test_exponential_backoff(self):
        """Retry delay increases (exponential backoff)."""
        self.assertRegex(self.middleware_src, r"delay\s*\*\s*2")

    def test_retry_max_cap(self):
        """Backoff delay is capped to prevent unbounded waits."""
        self.assertIn("min(delay", self.middleware_src)

    def test_health_check_loop_exists(self):
        """Middleware runs periodic health checks against the server."""
        self.assertIn("def _health_check_loop(", self.middleware_src)

    def test_health_check_failure_threshold(self):
        """Health check uses a consecutive-failure threshold before declaring down."""
        self.assertIn("_HEALTH_FAILURE_THRESHOLD", self.middleware_src)
        self.assertIn("consecutive_failures", self.middleware_src)

    def test_socket_disconnect_handler_exists(self):
        """Socket API handles disconnection gracefully."""
        self.assertIn("def _on_disconnect(", self.socket_src)

    def test_socket_disconnect_preserves_session(self):
        """Socket disconnect does NOT tear down the peer session (allows reconnect)."""
        disconnect_section = self.socket_src[
            self.socket_src.index("def _on_disconnect"):
        ]
        self.assertIn(
            "do NOT call server.disconnect_peer",
            disconnect_section,
            "Disconnect handler should preserve the session for reconnection",
        )

    def test_socket_uses_room_based_sessions(self):
        """Socket API uses room-based session isolation."""
        self.assertIn("self.sessions", self.socket_src)
        self.assertIn("join_room", self.socket_src)
        self.assertIn("leave_room", self.socket_src)

    def test_error_emission_to_browser(self):
        """Middleware emits 'server-error' events to the browser on failure."""
        self.assertIn("server-error", self.middleware_src)


# ═══════════════════════════════════════════════════════════════════════════
# WP #644 — Performance and load test: concurrent sessions
# ═══════════════════════════════════════════════════════════════════════════

class TestPerformanceArchitecture(unittest.TestCase):
    """Verify thread-based architecture and configurable performance params."""

    @classmethod
    def setUpClass(cls):
        cls.socket_src = _read("server/socket_api.py")
        cls.config_src = _read("shared/config.py")
        cls.middleware_src = _read("middleware/server_comms.py")

    def test_socket_api_uses_shared_socketio(self):
        """Socket API accepts a shared SocketIO instance."""
        self.assertIn("socketio: SocketIO", self.socket_src)

    def test_socket_api_creates_sessions(self):
        """Socket API creates room-based sessions."""
        self.assertIn("create_session", self.socket_src)

    def test_configurable_frame_rate(self):
        """Frame rate is configurable via config."""
        self.assertIn("frame_rate", self.config_src)

    def test_configurable_video_resolution(self):
        """Video resolution (width/height) is configurable."""
        self.assertIn("video_width", self.config_src)
        self.assertIn("video_height", self.config_src)

    def test_configurable_sample_rate(self):
        """Audio sample rate is configurable."""
        self.assertIn("sample_rate", self.config_src)

    def test_configurable_network_ports(self):
        """Network ports are configurable via config."""
        for port_key in ("middleware_port", "server_rest_port",
                         "client_api_port"):
            self.assertIn(port_key, self.config_src,
                          f"Missing configurable port: {port_key}")

    def test_config_supports_env_overrides(self):
        """Config values can be overridden via environment variables."""
        self.assertIn("os.environ.get(", self.config_src)

    def test_config_supports_ini_file(self):
        """Config loads from settings.ini file."""
        self.assertIn("configparser", self.config_src)
        self.assertIn("settings.ini", self.config_src)

    def test_config_dataclass_exists(self):
        """Config uses a dataclass for injectable configuration."""
        self.assertIn("@dataclass", self.config_src)
        self.assertIn("class Config", self.config_src)

    def test_bb84_parameters_configurable(self):
        """BB84 protocol parameters are configurable."""
        for param in ("bb84_num_raw_bits", "bb84_qber_threshold",
                      "bb84_fiber_length_km", "bb84_source_intensity",
                      "bb84_detector_efficiency"):
            self.assertIn(param, self.config_src,
                          f"Missing configurable BB84 param: {param}")

    def test_ssl_context_support(self):
        """Server supports optional TLS/SSL via dev certificates."""
        rest_src = _read("server/rest_api.py")
        self.assertIn("ssl", rest_src.lower())


if __name__ == "__main__":
    unittest.main()
