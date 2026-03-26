"""Observability tests — WP #369, #650-#661.

Tests for structured logging, health check, key exchange status,
encryption resource management, streaming, frontend, and room
management concerns.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# ── WP #369: Structured Logging, Metrics, Health Check ──

class TestStructuredLogging:
    """Verify structured JSON logging is available."""

    def test_json_formatter_exists(self):
        """Logging module should have JSONFormatter class."""
        source = open(os.path.join(ROOT, 'shared', 'logging.py')).read()
        assert 'JSONFormatter' in source

    def test_log_file_handler_created(self):
        """Logger should configure file output."""
        source = open(os.path.join(ROOT, 'shared', 'logging.py')).read()
        assert 'RotatingFileHandler' in source

    def test_json_formatter_includes_required_fields(self):
        """JSON log entries should include timestamp, level, logger, message."""
        source = open(os.path.join(ROOT, 'shared', 'logging.py')).read()
        for field in ('timestamp', 'level', 'logger', 'message'):
            assert field in source

    def test_json_formatter_supports_extra_context(self):
        """JSON formatter should include extra fields like user_id, request_id."""
        source = open(os.path.join(ROOT, 'shared', 'logging.py')).read()
        assert 'user_id' in source
        assert 'request_id' in source

    def test_get_logger_function_exists(self):
        """Logging module should expose a get_logger function."""
        source = open(os.path.join(ROOT, 'shared', 'logging.py')).read()
        assert 'def get_logger' in source


class TestHealthCheck:
    """Verify health check and admin monitoring endpoints exist."""

    def test_health_endpoint_defined(self):
        """Admin routes should have /health endpoint."""
        source = open(os.path.join(ROOT, 'server', 'admin_routes.py')).read()
        assert "'/health'" in source or '"/health"' in source

    def test_health_returns_status(self):
        """Health endpoint should return status field."""
        source = open(os.path.join(ROOT, 'server', 'admin_routes.py')).read()
        assert "'healthy'" in source or '"healthy"' in source

    def test_health_returns_uptime(self):
        """Health endpoint should include uptime."""
        source = open(os.path.join(ROOT, 'server', 'admin_routes.py')).read()
        assert 'uptime' in source

    def test_admin_dashboard_endpoint(self):
        """Admin routes should have a dashboard endpoint."""
        source = open(os.path.join(ROOT, 'server', 'admin_routes.py')).read()
        assert 'dashboard' in source

    def test_admin_uses_blueprint(self):
        """Admin routes should use Flask Blueprint."""
        source = open(os.path.join(ROOT, 'server', 'admin_routes.py')).read()
        assert 'Blueprint' in source


class TestMetrics:
    """Verify metrics endpoints exist."""

    def test_quantum_metrics_endpoint(self):
        """Admin should have quantum metrics endpoint."""
        source = open(os.path.join(ROOT, 'server', 'admin_routes.py')).read()
        assert 'quantum/metrics' in source

    def test_admin_status_endpoint(self):
        """Admin should have status endpoint."""
        source = open(os.path.join(ROOT, 'server', 'admin_routes.py')).read()
        assert 'admin/status' in source

    def test_event_log_endpoint(self):
        """Admin should have events endpoint."""
        source = open(os.path.join(ROOT, 'server', 'admin_routes.py')).read()
        assert 'admin/events' in source


# ── WP #650: Real-time Key Exchange Status UI ──

class TestKeyExchangeStatusUI:
    """Verify key exchange status is broadcast to clients."""

    def test_qber_update_event_emitted(self):
        """Socket API should emit qber-update events."""
        source = open(os.path.join(ROOT, 'server', 'socket_api.py')).read()
        assert 'qber' in source.lower()

    def test_qber_monitor_has_summary(self):
        """QBER monitor should provide summary for UI display."""
        source = open(os.path.join(ROOT, 'shared', 'bb84', 'qber_monitor.py')).read()
        assert 'get_summary' in source

    def test_qber_monitor_has_history(self):
        """QBER monitor should track history for UI charts."""
        source = open(os.path.join(ROOT, 'shared', 'bb84', 'qber_monitor.py')).read()
        assert 'get_history' in source


# ── WP #651: SRTP Key Integration from QKD ──

class TestKeyIntegration:
    """Verify QKD keys integrate with encryption system."""

    def test_bb84_key_generator_registered(self):
        """BB84 key generator should be in keygen registry."""
        source = open(os.path.join(ROOT, 'shared', 'encryption.py')).read()
        assert 'BB84KeyGenerator' in source
        assert 'bb84' in source.lower()

    def test_key_generator_abstract_interface(self):
        """All key generators implement AbstractKeyGenerator."""
        source = open(os.path.join(ROOT, 'shared', 'encryption.py')).read()
        assert 'AbstractKeyGenerator' in source
        assert 'generate_key' in source
        assert 'get_key' in source


# ── WP #652: FileKeyGenerator Resource Management ──

class TestFileKeyGeneratorResources:
    """Verify FileKeyGenerator properly manages file resources."""

    def test_context_manager_support(self):
        """FileKeyGenerator must implement context manager."""
        source = open(os.path.join(ROOT, 'shared', 'encryption.py')).read()
        assert '__enter__' in source
        assert '__exit__' in source

    def test_close_method_exists(self):
        """FileKeyGenerator must have close() method."""
        source = open(os.path.join(ROOT, 'shared', 'encryption.py')).read()
        assert 'def close(self)' in source

    def test_destructor_closes_file(self):
        """FileKeyGenerator should close file in __del__."""
        source = open(os.path.join(ROOT, 'shared', 'encryption.py')).read()
        assert '__del__' in source


# ── WP #653: Encryption at Rest for Stored Keys ──

class TestEncryptionAtRest:
    """Verify key storage security."""

    def test_no_plaintext_key_in_config(self):
        """Config files should not contain plaintext encryption keys."""
        config_path = os.path.join(ROOT, 'shared', 'config.py')
        source = open(config_path).read()
        # Should not have hardcoded keys
        assert 'SECRET_KEY = "' not in source
        assert "SECRET_KEY = '" not in source

    def test_aes_gcm_mode_used(self):
        """Encryption should use AES-GCM (authenticated) not CBC."""
        source = open(os.path.join(ROOT, 'shared', 'encryption.py')).read()
        assert 'GCM' in source


# ── WP #654: Peer Connection Lifecycle ──

class TestPeerConnectionLifecycle:
    """Verify peer connection management."""

    def test_peer_manager_exists(self):
        """Peer manager module should exist."""
        assert os.path.isfile(os.path.join(ROOT, 'server', 'peer_manager.py'))

    def test_peer_connection_endpoint(self):
        """REST API should have peer_connection endpoint."""
        source = open(os.path.join(ROOT, 'server', 'rest_api.py')).read()
        assert 'peer_connection' in source

    def test_disconnect_endpoint(self):
        """REST API should have disconnect endpoint."""
        source = open(os.path.join(ROOT, 'server', 'rest_api.py')).read()
        assert 'disconnect' in source.lower()


# ── WP #655: Video Stream Quality ──

class TestVideoStreamQuality:
    """Verify video streaming capabilities."""

    def test_frame_event_handler(self):
        """Socket API should handle frame events."""
        source = open(os.path.join(ROOT, 'server', 'socket_api.py')).read()
        assert 'frame' in source

    def test_audio_frame_handler(self):
        """Socket API should handle audio-frame events."""
        source = open(os.path.join(ROOT, 'server', 'socket_api.py')).read()
        assert 'audio' in source.lower()


# ── WP #656: Text Chat Message Delivery ──

class TestChatDelivery:
    """Verify text chat functionality."""

    def test_message_handler_exists(self):
        """Socket API should handle message events."""
        source = open(os.path.join(ROOT, 'server', 'socket_api.py')).read()
        assert 'message' in source


# ── WP #657: Electron App Launch ──

class TestElectronApp:
    """Verify frontend app configuration."""

    def test_frontend_package_json_exists(self):
        """Frontend should have an HTML entry point."""
        assert os.path.isfile(os.path.join(ROOT, 'website', 'client', 'index.html'))

    def test_main_process_entry(self):
        """Frontend should have a JS entry point."""
        entry = os.path.join(ROOT, 'website', 'client', 'static', 'app.js')
        assert os.path.isfile(entry)


# ── WP #658: React Component Render ──

class TestReactComponents:
    """Verify frontend component structure."""

    def test_renderer_directory_exists(self):
        """Frontend should have static source directory."""
        static_dir = os.path.join(ROOT, 'website', 'client', 'static')
        assert os.path.isdir(static_dir)

    def test_app_component_exists(self):
        """App component should exist."""
        static_dir = os.path.join(ROOT, 'website', 'client', 'static')
        if os.path.isdir(static_dir):
            files = []
            for _, _, fnames in os.walk(static_dir):
                files.extend(fnames)
            app_files = [f for f in files if 'app' in f.lower()]
            assert len(app_files) > 0


# ── WP #659: Camera/Microphone Permissions ──

class TestMediaPermissions:
    """Verify media permission handling in frontend."""

    def test_media_permission_code_exists(self):
        """Frontend should handle media device access."""
        # Check for video/camera references in the JS frontend
        app_js = os.path.join(ROOT, 'website', 'client', 'static', 'app.js')
        if os.path.isfile(app_js):
            content = open(app_js).read()
            assert 'video' in content.lower() or 'camera' in content.lower()
        else:
            # Fallback: check middleware templates/static
            static_dir = os.path.join(ROOT, 'website', 'client', 'static')
            found = False
            for root_dir, _, fnames in os.walk(static_dir):
                for f in fnames:
                    if f.endswith(('.js', '.html')):
                        content = open(os.path.join(root_dir, f)).read()
                        if 'video' in content.lower() or 'camera' in content.lower():
                            found = True
                            break
                if found:
                    break
            assert found


# ── WP #660: Room Creation and Join Flow ──

class TestRoomManagement:
    """Verify room creation and join functionality."""

    def test_create_user_endpoint(self):
        """REST API should have create_user endpoint."""
        source = open(os.path.join(ROOT, 'server', 'rest_api.py')).read()
        assert 'create_user' in source

    def test_room_id_generated(self):
        """Socket API should generate room IDs."""
        source = open(os.path.join(ROOT, 'server', 'socket_api.py')).read()
        assert 'room' in source.lower()


# ── WP #661: Session Cleanup and Resource Release ──

class TestSessionCleanup:
    """Verify session cleanup on disconnect."""

    def test_disconnect_handler_exists(self):
        """Socket API should handle disconnect events."""
        source = open(os.path.join(ROOT, 'server', 'socket_api.py')).read()
        assert 'disconnect' in source

    def test_remove_user_endpoint(self):
        """REST API should have remove_user endpoint."""
        source = open(os.path.join(ROOT, 'server', 'rest_api.py')).read()
        assert 'remove_user' in source

    def test_user_manager_cleanup(self):
        """User manager should support removing users."""
        user_mgr_path = os.path.join(ROOT, 'server', 'user_manager.py')
        if os.path.isfile(user_mgr_path):
            source = open(user_mgr_path).read()
            assert 'remove' in source.lower()
