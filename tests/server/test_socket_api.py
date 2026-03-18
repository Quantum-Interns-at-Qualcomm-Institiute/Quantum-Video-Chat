"""Tests for server/socket_api.py — SocketAPI class."""
import pytest
from unittest.mock import MagicMock, patch
from shared.exceptions import ServerError
from shared.endpoint import Endpoint


def _make_api(users=('u1', 'u2'), state=None):
    """Create a SocketAPI instance with a mock server."""
    from socket_api import SocketAPI
    from state import SocketState

    mock_server = MagicMock()
    mock_server.websocket_endpoint = Endpoint('127.0.0.1', 3000)
    api = SocketAPI(mock_server, users)
    if state:
        api.state = SocketState[state]
    return api


class TestSocketAPI:
    def test_init_sets_state(self):
        from state import SocketState
        api = _make_api(users=('u1', 'u2'))
        assert api.state == SocketState.INIT
        assert 'u1' in api.users
        assert 'u2' in api.users

    def test_has_all_users_false(self):
        api = _make_api()
        api.users = {'u1': None, 'u2': 'connected'}
        assert api.has_all_users() is False

    def test_has_all_users_true(self):
        api = _make_api()
        api.users = {'u1': 'conn1', 'u2': 'conn2'}
        assert api.has_all_users() is True

    def test_has_all_users_empty(self):
        api = _make_api(users=())
        assert api.has_all_users() is True

    def test_verify_connection_known(self):
        api = _make_api(users=('u1',))
        assert api.verify_connection('u1') is True

    def test_verify_connection_unknown(self):
        api = _make_api(users=('u1',))
        assert api.verify_connection('u2') is False

    def test_kill_when_not_live_raises(self):
        api = _make_api(state='INIT')
        with pytest.raises(ServerError, match="Cannot kill"):
            api.kill()

    def test_kill_when_live(self):
        from state import SocketState
        api = _make_api(state='LIVE')
        api.socketio = MagicMock()
        api.kill()
        assert api.state == SocketState.INIT

    def test_kill_when_open(self):
        from state import SocketState
        api = _make_api(state='OPEN')
        api.socketio = MagicMock()
        api.kill()
        assert api.state == SocketState.INIT
