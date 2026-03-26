"""Tests for SocketAPI event handlers in server/socket_api.py."""
from unittest.mock import MagicMock, patch


def _make_api():
    """Create a SocketAPI instance with a mock server and mock socketio."""
    from socket_api import SocketAPI
    mock_server = MagicMock()
    mock_socketio = MagicMock()
    return SocketAPI(mock_server, mock_socketio)


class TestSocketAPIOnConnect:
    def test_valid_user_accepted(self):
        api = _make_api()
        session_id = api.create_session(("user1", "user2"))

        mock_req = MagicMock()
        mock_req.sid = "sid123"
        with patch("socket_api.flask_request", new=mock_req), \
             patch("socket_api.join_room") as mock_join:
            api._on_connect({"user_id": "user1", "session_id": session_id})

        assert api.sids.get("sid123") == (session_id, "user1")
        mock_join.assert_called_once_with(session_id)

    def test_unknown_user_rejected(self):
        api = _make_api()
        session_id = api.create_session(("user1",))
        result = api._on_connect({"user_id": "unknown_user", "session_id": session_id})
        assert result is False

    def test_no_auth_dict_rejected(self):
        api = _make_api()
        result = api._on_connect("user1")
        assert result is False

    def test_unknown_session_rejected(self):
        api = _make_api()
        result = api._on_connect({"user_id": "user1", "session_id": "nonexistent"})
        assert result is False

    def test_no_session_id_rejected(self):
        api = _make_api()
        result = api._on_connect({"user_id": "user1"})
        assert result is False

    def test_room_id_emitted_when_all_users_connect(self):
        """When has_all_users() is True after on_connect, room-id is emitted to the room."""
        api = _make_api()
        session_id = api.create_session(("user1", "user2"))

        mock_req = MagicMock()

        # First user connects
        mock_req.sid = "sid1"
        with patch("socket_api.flask_request", new=mock_req), \
             patch("socket_api.join_room"):
            api._on_connect({"user_id": "user1", "session_id": session_id})
        api.socketio.emit.assert_not_called()

        # Second user connects
        mock_req.sid = "sid2"
        with patch("socket_api.flask_request", new=mock_req), \
             patch("socket_api.join_room"):
            api._on_connect({"user_id": "user2", "session_id": session_id})

        # Now room-id should be emitted to the session room
        api.socketio.emit.assert_called_once()
        event_name = api.socketio.emit.call_args[0][0]
        room_id = api.socketio.emit.call_args[0][1]
        assert event_name == "room-id"
        assert isinstance(room_id, str)
        assert len(room_id) == 5
        # Should be emitted to the session room
        assert api.socketio.emit.call_args[1]["to"] == session_id


class TestSocketAPIOnDisconnect:
    def test_sid_removed_on_disconnect(self):
        api = _make_api()
        session_id = api.create_session(("user1", "user2"))
        api.sids = {
            "sid1": (session_id, "user1"),
            "sid2": (session_id, "user2"),
        }

        mock_req = MagicMock()
        mock_req.sid = "sid1"
        with patch("socket_api.flask_request", new=mock_req), \
             patch("socket_api.leave_room") as mock_leave:
            api._on_disconnect()

        assert "sid1" not in api.sids
        assert "sid2" in api.sids
        mock_leave.assert_called_once_with(session_id)

    def test_disconnect_does_not_call_disconnect_peer(self):
        """Transient socket disconnections should NOT tear down the peer
        session.  Only the explicit REST /disconnect_peer endpoint should."""
        api = _make_api()
        session_id = api.create_session(("user1", "user2"))
        api.sids = {
            "sid1": (session_id, "user1"),
            "sid2": (session_id, "user2"),
        }

        mock_req = MagicMock()
        mock_req.sid = "sid1"
        with patch("socket_api.flask_request", new=mock_req), \
             patch("socket_api.leave_room"):
            api._on_disconnect()

        api.server.disconnect_peer.assert_not_called()


class TestSocketAPIOnFrame:
    def test_frame_relayed_to_session_room(self):
        api = _make_api()
        session_id = api.create_session(("user1", "user2"))
        api.sids = {
            "sid1": (session_id, "user1"),
            "sid2": (session_id, "user2"),
        }

        mock_req = MagicMock()
        mock_req.sid = "sid1"
        with patch("socket_api.flask_request", new=mock_req):
            api._on_frame({"frame": [1, 2, 3], "width": 640, "height": 480})

        api.socketio.emit.assert_called_once_with("frame", {
            "frame": [1, 2, 3],
            "width": 640,
            "height": 480,
            "sender": "user1",
        }, to=session_id, skip_sid="sid1")

    def test_frame_ignored_for_unknown_sid(self):
        api = _make_api()
        mock_req = MagicMock()
        mock_req.sid = "unknown_sid"
        with patch("socket_api.flask_request", new=mock_req):
            api._on_frame({"frame": [1, 2, 3], "width": 640, "height": 480})
        api.socketio.emit.assert_not_called()


class TestSocketAPIOnAudioFrame:
    def test_audio_frame_relayed_to_session_room(self):
        api = _make_api()
        session_id = api.create_session(("user1", "user2"))
        api.sids = {
            "sid1": (session_id, "user1"),
            "sid2": (session_id, "user2"),
        }

        mock_req = MagicMock()
        mock_req.sid = "sid1"
        with patch("socket_api.flask_request", new=mock_req):
            api._on_audio_frame({"audio": [0.1, 0.2], "sample_rate": 8000})

        api.socketio.emit.assert_called_once_with("audio-frame", {
            "audio": [0.1, 0.2],
            "sample_rate": 8000,
            "sender": "user1",
        }, to=session_id, skip_sid="sid1")
