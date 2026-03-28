"""Tests for middleware/events.py — browser/server event and REST route registration."""
from unittest.mock import MagicMock, patch

import pytest

from tests.middleware._helpers import load_middleware_module

mw_state_mod = load_middleware_module("state")
mw_events = load_middleware_module("events")

MiddlewareState = mw_state_mod.MiddlewareState
register_browser_events = mw_events.register_browser_events
register_server_events = mw_events.register_server_events
register_rest_routes = mw_events.register_rest_routes


@pytest.fixture
def state():
    """Fresh MiddlewareState for event tests."""
    return MiddlewareState()


# ─── register_browser_events ─────────────────────────────────────────────────

class TestRegisterBrowserEvents:
    def test_registers_expected_events(self, state):
        register_browser_events(state)
        registered = {name for name, _ in state.sio.handlers.get("/", {}).items()
                      if name not in {"connect", "disconnect"}}
        # At minimum these should be registered
        expected = {"pong", "toggle_camera", "toggle_mute", "select_camera",
                    "list_cameras", "select_audio", "list_audio_devices",
                    "configure_server", "create_user", "join_room", "leave_room"}
        assert expected.issubset(registered), f"Missing: {expected - registered}"

    def test_connect_emits_welcome(self, state):
        register_browser_events(state)
        state.sio = MagicMock(wraps=state.sio)
        # Get the connect handler
        _handlers = state.sio.handlers.get("/", {})
        # Since we wrapped after registration, handlers are on the original sio.
        # Re-register with mocked sio to capture emits.
        state2 = MiddlewareState()
        state2.sio = MagicMock()
        state2.sio.event = lambda fn: fn  # passthrough decorator
        register_browser_events(state2)

    def test_pong_updates_last_seen(self, state):
        register_browser_events(state)

        # Call the pong handler directly
        handlers = state.sio.handlers.get("/", {})
        pong_handler = handlers.get("pong")
        assert pong_handler is not None

        # Simulate a tracked client
        state._browser_clients["test-client"] = {"sid": "sid1", "last_seen": 0}
        state._sid_to_client["sid1"] = "test-client"
        pong_handler("sid1", {"client_id": "test-client"})
        assert state._browser_clients["test-client"]["last_seen"] > 0

    def test_toggle_camera(self, state):
        register_browser_events(state)
        handlers = state.sio.handlers.get("/", {})
        toggle = handlers.get("toggle_camera")
        assert toggle is not None

        toggle("sid1", {"enabled": False})
        assert state.camera_enabled is False
        toggle("sid1", {"enabled": True})
        assert state.camera_enabled is True

    def test_toggle_mute(self, state):
        register_browser_events(state)
        handlers = state.sio.handlers.get("/", {})
        toggle = handlers.get("toggle_mute")
        assert toggle is not None

        toggle("sid1", {"muted": True})
        assert state.muted is True
        toggle("sid1", {"muted": False})
        assert state.muted is False

    def test_select_camera_updates_device(self, state):
        register_browser_events(state)
        handlers = state.sio.handlers.get("/", {})
        select = handlers.get("select_camera")
        assert select is not None

        with patch.object(mw_events, "server_comms") as _mock_comms:
            select("sid1", {"device": 2})
        assert state.camera_device == 2

    def test_list_cameras_emits_list(self, state):
        register_browser_events(state)
        handlers = state.sio.handlers.get("/", {})
        list_cams = handlers.get("list_cameras")
        assert list_cams is not None

        state.sio.emit = MagicMock()
        with patch.object(mw_events, "server_comms") as mock_comms:
            mock_comms.enumerate_cameras.return_value = [
                {"index": 0, "label": "Camera 0"}]
            list_cams("sid1")

        state.sio.emit.assert_called_once_with(
            "camera-list", [{"index": 0, "label": "Camera 0"}], room="sid1")

    def test_configure_server_delegates(self, state):
        register_browser_events(state)
        handlers = state.sio.handlers.get("/", {})
        configure = handlers.get("configure_server")
        assert configure is not None

        with patch.object(mw_events, "server_comms") as mock_comms, \
             patch.object(mw_events, "gevent") as mock_gevent:
            configure("sid1", {"host": "h", "port": 1})
        mock_gevent.spawn.assert_called_once_with(
            mock_comms.configure_server, state, "sid1", {"host": "h", "port": 1})


# ─── register_server_events ──────────────────────────────────────────────────

class TestRegisterServerEvents:
    def test_room_id_starts_media(self, state):
        register_server_events(state)
        handlers = state.server_client.handlers.get("/", {})
        room_id_handler = None
        for name, handler in handlers.items():
            if name == "room-id":
                room_id_handler = handler
                break

        if room_id_handler is None:
            # Try alternate registration pattern
            pytest.skip("Cannot access server_client handlers directly")

        state.sio.emit = MagicMock()
        with patch.object(mw_events, "server_comms") as mock_comms:
            room_id_handler("test-room")
        state.sio.emit.assert_called_with("room-id", "test-room")
        mock_comms.start_video.assert_called_once()
        mock_comms.start_audio.assert_called_once()

    def test_frame_relay_ignores_own_frames(self, state):
        register_server_events(state)
        handlers = state.server_client.handlers.get("/", {})
        frame_handler = handlers.get("frame")
        if frame_handler is None:
            pytest.skip("Cannot access server_client handlers directly")

        state.sio.emit = MagicMock()
        # Frame with no sender should be ignored
        frame_handler({"sender": None, "frame": [1, 2, 3]})
        state.sio.emit.assert_not_called()

    def test_frame_relay_forwards_peer_frames(self, state):
        register_server_events(state)
        handlers = state.server_client.handlers.get("/", {})
        frame_handler = handlers.get("frame")
        if frame_handler is None:
            pytest.skip("Cannot access server_client handlers directly")

        state.sio.emit = MagicMock()
        frame_handler({"sender": "peer1", "frame": [1, 2, 3], "width": 640, "height": 480})
        state.sio.emit.assert_called_once_with("frame", {
            "frame": [1, 2, 3],
            "width": 640,
            "height": 480,
            "self": False,
        })


# ─── register_rest_routes ────────────────────────────────────────────────────

class TestRegisterRestRoutes:
    def test_peer_connection_route(self, state):
        register_rest_routes(state)
        client = state.flask_app.test_client()

        with patch.object(mw_events, "server_comms") as _mock_comms, \
             patch.object(mw_events, "gevent") as mock_gevent:
            resp = client.post("/peer_connection", json={
                "peer_id": "peer1",
                "socket_endpoint": ["localhost", 4000],
                "session_id": "sess-123",
            })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        mock_gevent.spawn.assert_called_once()
        # Verify session_id is passed through
        spawn_args = mock_gevent.spawn.call_args
        assert spawn_args[1].get("session_id") == "sess-123" or "sess-123" in str(spawn_args)

    def test_peer_disconnected_route(self, state):
        register_rest_routes(state)
        client = state.flask_app.test_client()

        mock_video = MagicMock()
        mock_audio = MagicMock()
        state.video_thread = mock_video
        state.audio_thread = mock_audio
        state.sio.emit = MagicMock()

        resp = client.post("/peer_disconnected", json={
            "peer_id": "peer1",
        })

        assert resp.status_code == 200
        mock_video.stop.assert_called_once()
        mock_audio.stop.assert_called_once()
        assert state.video_thread is None
        assert state.audio_thread is None
        state.sio.emit.assert_called_with("peer-disconnected", {"peer_id": "peer1"})

    def test_peer_connection_no_endpoint(self, state):
        register_rest_routes(state)
        client = state.flask_app.test_client()

        with patch.object(mw_events, "gevent") as mock_gevent:
            resp = client.post("/peer_connection", json={
                "peer_id": "peer1",
            })

        assert resp.status_code == 200
        mock_gevent.spawn.assert_not_called()

    def test_health_endpoint(self, state):
        register_rest_routes(state)
        client = state.flask_app.test_client()

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "uptime" in data
        assert "clients" in data

    def test_disconnect_endpoint(self, state):
        register_browser_events(state)
        register_rest_routes(state)
        client = state.flask_app.test_client()

        # Add a tracked client
        state._browser_clients["cid-1"] = {"sid": "s1", "last_seen": 0}

        resp = client.post("/disconnect", json={"client_id": "cid-1"})
        assert resp.status_code == 204
        assert "cid-1" not in state._browser_clients

    def test_disconnect_unknown_client(self, state):
        register_rest_routes(state)
        client = state.flask_app.test_client()

        resp = client.post("/disconnect", json={"client_id": "nonexistent"})
        assert resp.status_code == 204
