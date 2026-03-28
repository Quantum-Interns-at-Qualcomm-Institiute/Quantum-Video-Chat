"""Tests for middleware/server_comms.py — QKD server communication."""
from unittest.mock import MagicMock, patch

import pytest

from tests.middleware._helpers import load_middleware_module

mw_state = load_middleware_module("state")
mw_comms = load_middleware_module("server_comms")

MiddlewareState = mw_state.MiddlewareState
configure_server = mw_comms.configure_server
create_user = mw_comms.create_user
join_room = mw_comms.join_room
leave_room = mw_comms.leave_room
connect_to_session_ws = mw_comms.connect_to_session_ws
start_video = mw_comms.start_video
start_audio = mw_comms.start_audio
enumerate_cameras = mw_comms.enumerate_cameras
enumerate_audio_devices = mw_comms.enumerate_audio_devices
start_health_checks = mw_comms.start_health_checks
_health_check_loop = mw_comms._health_check_loop
_HEALTH_FAILURE_THRESHOLD = mw_comms._HEALTH_FAILURE_THRESHOLD


@pytest.fixture
def state():
    """Fresh MiddlewareState with mocked sio.emit and server_client."""
    s = MiddlewareState()
    s.sio = MagicMock()
    s.server_client = MagicMock()
    s.server_client.connected = False
    return s


# ─── configure_server ─────────────────────────────────────────────────────────

class TestConfigureServer:
    def test_emits_error_when_no_host(self, state):
        configure_server(state, "sid1", {"host": "", "port": 5050})
        state.sio.emit.assert_called_once_with("server-error", "No host provided.", room="sid1")

    @patch("mw_server_comms.urllib.request.urlopen")
    def test_successful_connection(self, mock_urlopen, state):
        import json
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({"api_state": "idle", "user_count": 0}).encode()
        mock_resp.status = 200
        mock_urlopen.return_value = mock_resp

        with patch.object(mw_comms, "start_health_checks"):
            configure_server(state, "sid1", {"host": "10.0.0.1", "port": 5050})

        assert state.server_host == "10.0.0.1"
        assert state.server_port == 5050
        assert state.server_alive is True
        state.sio.emit.assert_called_with("server-connected", room="sid1")

    @patch("mw_server_comms.urllib.request.urlopen")
    def test_connection_refused(self, mock_urlopen, state):
        mock_urlopen.side_effect = ConnectionError("refused")

        configure_server(state, "sid1", {"host": "10.0.0.1", "port": 9999})
        state.sio.emit.assert_called_once_with(
            "server-error",
            "Could not connect to 10.0.0.1:9999 -- refused",
            room="sid1",
        )

    @patch("mw_server_comms.urllib.request.urlopen")
    def test_generic_exception(self, mock_urlopen, state):
        mock_urlopen.side_effect = OSError("timeout")

        configure_server(state, "sid1", {"host": "10.0.0.1", "port": 9999})
        call_args = state.sio.emit.call_args
        assert call_args[0][0] == "server-error"
        assert "timeout" in call_args[0][1]


# ─── create_user ──────────────────────────────────────────────────────────────

class TestCreateUser:
    def test_error_when_no_server(self, state):
        create_user(state, "sid1")
        state.sio.emit.assert_called_once_with(
            "server-error", "Not connected to a server.", room="sid1")

    @patch("mw_server_comms.requests")
    def test_successful_registration(self, mock_requests, state):
        state.server_host = "localhost"
        state.server_port = 5050
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"user_id": "abc123"}
        mock_requests.post.return_value = mock_resp

        create_user(state, "sid1")
        assert state.user_id == "abc123"
        state.sio.emit.assert_called_with(
            "user-registered", {"user_id": "abc123"}, room="sid1")

    @patch("mw_server_comms.requests")
    def test_registration_failure(self, mock_requests, state):
        import requests as real_requests
        state.server_host = "localhost"
        state.server_port = 5050
        mock_requests.post.side_effect = real_requests.RequestException("nope")
        mock_requests.RequestException = real_requests.RequestException

        create_user(state, "sid1")
        call_args = state.sio.emit.call_args
        assert call_args[0][0] == "server-error"
        assert "nope" in call_args[0][1]


# ─── join_room ────────────────────────────────────────────────────────────────

class TestJoinRoom:
    def test_error_when_no_server(self, state):
        join_room(state, "sid1")
        state.sio.emit.assert_called_once_with(
            "server-error", "Not connected to a server.", room="sid1")

    def test_error_when_no_user_id(self, state):
        state.server_host = "localhost"
        state.server_port = 5050
        join_room(state, "sid1")
        state.sio.emit.assert_called_once_with(
            "server-error", "Not registered with server yet.", room="sid1")

    def test_waiting_for_peer_when_no_peer_id(self, state):
        state.server_host = "localhost"
        state.server_port = 5050
        state.user_id = "user1"
        join_room(state, "sid1")
        state.sio.emit.assert_called_once_with(
            "waiting-for-peer", {"user_id": "user1"}, room="sid1")

    def test_error_connecting_to_self(self, state):
        state.server_host = "localhost"
        state.server_port = 5050
        state.user_id = "user1"
        join_room(state, "sid1", peer_id="user1")
        call_args = state.sio.emit.call_args
        assert call_args[0][0] == "server-error"
        assert "yourself" in call_args[0][1]

    @patch("mw_server_comms.requests")
    def test_successful_peer_connection(self, mock_requests, state):
        state.server_host = "localhost"
        state.server_port = 5050
        state.user_id = "user1"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "socket_endpoint": ("localhost", 4000),
            "session_id": "sess-123",
        }
        mock_requests.post.return_value = mock_resp

        with patch.object(mw_comms, "connect_to_session_ws") as mock_connect:
            join_room(state, "sid1", peer_id="user2")
            mock_connect.assert_called_once_with(state, ("localhost", 4000), "user2", session_id="sess-123")

    @patch("mw_server_comms.requests")
    def test_peer_connection_server_error(self, mock_requests, state):
        state.server_host = "localhost"
        state.server_port = 5050
        state.user_id = "user1"
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"error_message": "Peer not found"}
        mock_requests.post.return_value = mock_resp

        join_room(state, "sid1", peer_id="user2")
        call_args = state.sio.emit.call_args
        assert call_args[0][0] == "server-error"
        assert "Peer not found" in call_args[0][1]


# ─── leave_room ───────────────────────────────────────────────────────────────

class TestLeaveRoom:
    def test_stops_video_thread(self, state):
        mock_thread = MagicMock()
        state.video_thread = mock_thread
        leave_room(state, "sid1")
        mock_thread.stop.assert_called_once()
        assert state.video_thread is None

    def test_stops_audio_thread(self, state):
        mock_thread = MagicMock()
        state.audio_thread = mock_thread
        leave_room(state, "sid1")
        mock_thread.stop.assert_called_once()
        assert state.audio_thread is None

    def test_disconnects_server_client(self, state):
        state.server_client.connected = True
        leave_room(state, "sid1")
        state.server_client.disconnect.assert_called_once()

    @patch("mw_server_comms.requests")
    def test_posts_disconnect_peer(self, mock_requests, state):
        state.server_host = "localhost"
        state.server_port = 5050
        state.user_id = "user1"
        leave_room(state, "sid1")
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "/disconnect_peer" in call_args[0][0]


# ─── connect_to_session_ws ───────────────────────────────────────────────────

class TestConnectToSessionWs:
    @patch("shared.ssl_utils.get_ssl_context", return_value=None)
    @patch("mw_server_comms.gevent")
    def test_successful_first_attempt(self, mock_gevent, _mock_ssl, state):  # noqa: PT019
        state.server_client.connected = False
        state.user_id = "user1"
        state.server_client.connect = MagicMock()

        connect_to_session_ws(state, ("localhost", 4000), "peer1", session_id="sess-123")
        state.server_client.connect.assert_called_once_with(
            "http://localhost:4000",
            auth={"user_id": "user1", "session_id": "sess-123"},
            wait_timeout=10,
        )

    @patch("shared.ssl_utils.get_ssl_context", return_value=None)
    @patch("mw_server_comms.gevent")
    def test_successful_without_session_id(self, mock_gevent, _mock_ssl, state):  # noqa: PT019
        state.server_client.connected = False
        state.user_id = "user1"
        state.server_client.connect = MagicMock()

        connect_to_session_ws(state, ("localhost", 4000), "peer1")
        state.server_client.connect.assert_called_once_with(
            "http://localhost:4000",
            auth={"user_id": "user1"},
            wait_timeout=10,
        )

    @patch("mw_server_comms.gevent")
    def test_disconnects_if_already_connected(self, mock_gevent, state):
        state.server_client.connected = True
        state.user_id = "user1"

        connect_to_session_ws(state, ("localhost", 4000), "peer1", session_id="sess-123")
        state.server_client.disconnect.assert_called_once()

    @patch("mw_server_comms.gevent")
    def test_retries_on_failure(self, mock_gevent, state):
        state.server_client.connected = False
        state.user_id = "user1"
        # Fail twice, succeed third time
        state.server_client.connect = MagicMock(
            side_effect=[Exception("fail"), Exception("fail"), None])

        connect_to_session_ws(state, ("localhost", 4000), "peer1", session_id="sess-123")
        assert state.server_client.connect.call_count == 3

    @patch("mw_server_comms.gevent")
    def test_emits_error_after_max_attempts(self, mock_gevent, state):
        state.server_client.connected = False
        state.user_id = "user1"
        state.server_client.connect = MagicMock(side_effect=Exception("fail"))

        connect_to_session_ws(state, ("localhost", 4000), "peer1", session_id="sess-123")
        assert state.server_client.connect.call_count == 5
        state.sio.emit.assert_called_once()
        assert state.sio.emit.call_args[0][0] == "server-error"


# ─── enumerate_cameras ────────────────────────────────────────────────────────

class TestEnumerateCameras:
    @patch("mw_server_comms.os")
    def test_always_includes_mock_devices(self, mock_os):
        # Patch cv2 to return no real cameras
        mock_os.devnull = "/dev/null"
        mock_os.open.return_value = 99
        mock_os.dup.return_value = 100
        mock_os.O_WRONLY = 1

        with patch.dict("sys.modules", {"cv2": MagicMock()}) as mods:
            mock_cv2 = mods["cv2"]
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = False
            mock_cv2.VideoCapture.return_value = mock_cap

            devices = enumerate_cameras(max_devices=2)

        # Should have the two mock devices at minimum
        labels = [d["label"] for d in devices]
        assert "Test Pattern A" in labels
        assert "Test Pattern B" in labels


# ─── enumerate_audio_devices ──────────────────────────────────────────────────

class TestEnumerateAudioDevices:
    def test_always_includes_mock_devices(self):
        with patch.dict("sys.modules", {"pyaudio": MagicMock()}) as mods:
            mock_pa_instance = MagicMock()
            mock_pa_instance.get_device_count.return_value = 0
            mods["pyaudio"].PyAudio.return_value = mock_pa_instance

            devices = enumerate_audio_devices()

        labels = [d["label"] for d in devices]
        assert "Test Tone A" in labels
        assert "Test Tone B" in labels


# ─── start_video / start_audio ────────────────────────────────────────────────

class TestStartVideo:
    @patch("mw_server_comms.VideoThread")
    def test_starts_new_thread(self, MockVideoThread, state):
        mock_thread = MagicMock()
        MockVideoThread.return_value = mock_thread

        start_video(state, "room1")
        MockVideoThread.assert_called_once()
        mock_thread.start.assert_called_once()
        assert state.video_thread is mock_thread

    @patch("mw_server_comms.VideoThread")
    def test_stops_existing_thread(self, MockVideoThread, state):
        old_thread = MagicMock()
        old_thread.is_alive.return_value = True
        state.video_thread = old_thread

        new_thread = MagicMock()
        MockVideoThread.return_value = new_thread

        start_video(state, "room1")
        old_thread.stop.assert_called_once()
        old_thread.join.assert_called_once_with(timeout=2)


class TestStartAudio:
    def test_starts_new_thread(self, state):
        # AudioThread is imported locally inside start_audio via `from audio import AudioThread`
        mock_thread = MagicMock()
        with patch.dict("sys.modules", {}):
            mw_audio = load_middleware_module("audio")
            with patch.object(mw_audio, "AudioThread", return_value=mock_thread) as MockAudioThread:
                # Ensure the local import in start_audio picks up the patched module
                import sys as _sys
                _sys.modules["audio"] = mw_audio
                try:
                    start_audio(state, "room1")
                    MockAudioThread.assert_called_once()
                    mock_thread.start.assert_called_once()
                    assert state.audio_thread is mock_thread
                finally:
                    pass


# ─── health checks ───────────────────────────────────────────────────────────

class TestHealthChecks:
    def test_failure_threshold_is_two(self):
        assert _HEALTH_FAILURE_THRESHOLD == 2

    @patch("mw_server_comms.gevent")
    def test_start_health_checks_spawns_greenlet(self, mock_gevent, state):
        state.health_greenlet = None
        start_health_checks(state)
        mock_gevent.spawn.assert_called_once_with(_health_check_loop, state)

    @patch("mw_server_comms.gevent")
    def test_start_health_checks_idempotent(self, mock_gevent, state):
        mock_greenlet = MagicMock()
        mock_greenlet.dead = False
        state.health_greenlet = mock_greenlet
        start_health_checks(state)
        mock_gevent.spawn.assert_not_called()
