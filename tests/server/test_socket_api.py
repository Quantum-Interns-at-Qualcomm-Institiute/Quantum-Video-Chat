"""Tests for server/socket_api.py -- SocketAPI class."""
from unittest.mock import MagicMock


def _make_api():
    """Create a SocketAPI instance with a mock server and mock socketio."""
    from socket_api import SocketAPI

    mock_server = MagicMock()
    mock_socketio = MagicMock()
    return SocketAPI(mock_server, mock_socketio)


class TestSocketAPI:
    def test_init_creates_instance(self):
        api = _make_api()
        assert api.sessions == {}
        assert api.sids == {}

    def test_create_session(self):
        api = _make_api()
        session_id = api.create_session(("u1", "u2"))
        assert session_id in api.sessions
        assert api.sessions[session_id] == {"u1", "u2"}

    def test_create_session_returns_unique_ids(self):
        api = _make_api()
        s1 = api.create_session(("u1", "u2"))
        s2 = api.create_session(("u3", "u4"))
        assert s1 != s2
