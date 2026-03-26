"""Tests for middleware/state.py — MiddlewareState defaults and helpers."""
import os
from unittest.mock import patch

from tests.middleware._helpers import load_middleware_module

mw_state = load_middleware_module("state")
MiddlewareState = mw_state.MiddlewareState
MIDDLEWARE_PORT = mw_state.MIDDLEWARE_PORT
WIDTH = mw_state.WIDTH
HEIGHT = mw_state.HEIGHT


class TestConstants:
    def test_default_dimensions(self):
        assert WIDTH == 640
        assert HEIGHT == 480

    def test_default_middleware_port(self):
        assert MIDDLEWARE_PORT == 5001

    def test_default_server_host_from_env(self):
        with patch.dict(os.environ, {"QUANTUM_SERVER_HOST": "10.0.0.5"}):
            mod = load_middleware_module("state", fresh=True)
            assert mod.DEFAULT_SERVER_HOST == "10.0.0.5"

    def test_default_server_port_from_env(self):
        with patch.dict(os.environ, {"QUANTUM_SERVER_PORT": "9999"}):
            mod = load_middleware_module("state", fresh=True)
            assert mod.DEFAULT_SERVER_PORT == 9999


class TestMiddlewareStateDefaults:
    def test_server_fields_default(self):
        s = MiddlewareState()
        assert s.server_host == ""
        assert s.server_port == 0
        assert s.server_alive is False

    def test_identity_defaults(self):
        s = MiddlewareState()
        assert s.user_id == ""
        assert s.middleware_port == MIDDLEWARE_PORT

    def test_video_defaults(self):
        s = MiddlewareState()
        assert s.video_thread is None
        assert s.camera_enabled is True
        assert s.camera_device == 0

    def test_audio_defaults(self):
        s = MiddlewareState()
        assert s.audio_thread is None
        assert s.muted is False
        assert s.audio_device == 0

    def test_health_greenlet_default(self):
        s = MiddlewareState()
        assert s.health_greenlet is None

    def test_sio_and_flask_created(self):
        s = MiddlewareState()
        assert s.sio is not None
        assert s.flask_app is not None
        assert s.app is not None
        assert s.server_client is not None


class TestServerUrl:
    @patch("shared.ssl_utils.get_ssl_context", return_value=None)
    def test_builds_url_with_path(self, _mock_ssl):  # noqa: PT019
        s = MiddlewareState()
        s.server_host = "example.com"
        s.server_port = 8080
        assert s.server_url("/admin/status") == "http://example.com:8080/admin/status"

    @patch("shared.ssl_utils.get_ssl_context", return_value=None)
    def test_builds_url_root(self, _mock_ssl):  # noqa: PT019
        s = MiddlewareState()
        s.server_host = "192.168.1.1"
        s.server_port = 5050
        assert s.server_url("/") == "http://192.168.1.1:5050/"

    @patch("shared.ssl_utils.get_ssl_context", return_value=None)
    def test_empty_host_still_formats(self, _mock_ssl):  # noqa: PT019
        s = MiddlewareState()
        assert s.server_url("/test") == "http://:0/test"
