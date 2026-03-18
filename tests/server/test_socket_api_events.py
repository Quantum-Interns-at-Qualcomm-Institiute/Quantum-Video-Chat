"""Tests for SocketAPI event handlers and run() method in server/socket_api.py."""
import pytest
from unittest.mock import MagicMock, patch
from state import SocketState
from shared.exceptions import ServerError
from shared.endpoint import Endpoint


def _make_api(users=('u1', 'u2'), state=None):
    """Create a SocketAPI instance with a mock server."""
    from socket_api import SocketAPI
    mock_server = MagicMock()
    mock_server.websocket_endpoint = Endpoint('127.0.0.1', 3000)
    api = SocketAPI(mock_server, users)
    if state:
        api.state = SocketState[state]
    return api


class TestSocketAPIInit:
    def test_start_creates_daemon_thread(self):
        api = _make_api(users=('user1', 'user2'))
        with patch.object(api, '_run'):
            api.start()
            assert api._thread.daemon is True


class TestSocketAPIOnConnect:
    def test_valid_user_accepted(self):
        api = _make_api(users=('user1', 'user2'), state='LIVE')

        mock_req = MagicMock()
        mock_req.sid = 'sid123'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_connect('user1')

        assert api.sids.get('sid123') == 'user1'

    def test_valid_user_accepted_via_auth_dict(self):
        """flask_socketio passes auth as a dict — verify extraction."""
        api = _make_api(users=('user1', 'user2'), state='LIVE')

        mock_req = MagicMock()
        mock_req.sid = 'sid456'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_connect({'user_id': 'user1'})

        assert api.sids.get('sid456') == 'user1'

    def test_unknown_user_rejected(self):
        api = _make_api(users=('user1',), state='LIVE')
        result = api._on_connect('unknown_user')
        assert result is False

    def test_wrong_state_rejected(self):
        """Connections should be rejected when state is INIT (not yet ready)."""
        api = _make_api(users=('user1',), state='INIT')
        result = api._on_connect('user1')
        assert result is False

    def test_reconnection_accepted_when_open(self):
        """Connections should be accepted when state is OPEN (reconnection)."""
        api = _make_api(users=('user1',), state='OPEN')

        mock_req = MagicMock()
        mock_req.sid = 'sid_reconnect'
        with patch('socket_api.flask_request', new=mock_req):
            result = api._on_connect('user1')

        assert result is not False
        assert api.sids.get('sid_reconnect') == 'user1'

    def test_state_becomes_open_when_all_users_connected(self):
        """When has_all_users() is True after on_connect, state goes OPEN."""
        api = _make_api(users=('user1', 'user2'), state='LIVE')
        # Pre-set both users as connected so has_all_users() returns True
        api.users['user1'] = 'sid1'
        api.users['user2'] = 'sid2'

        mock_req = MagicMock()
        mock_req.sid = 'sid2'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_connect('user2')

        assert api.state == SocketState.OPEN


class TestSocketAPIOnDisconnect:
    def test_sid_removed_on_disconnect(self):
        api = _make_api(state='OPEN')
        api.sids = {'sid1': 'user1', 'sid2': 'user2'}

        mock_req = MagicMock()
        mock_req.sid = 'sid1'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_disconnect()

        assert 'sid1' not in api.sids
        assert 'sid2' in api.sids

    def test_state_reverts_to_live_when_all_disconnected(self):
        """When all users disconnect, state reverts to LIVE (not INIT) so
        reconnections are accepted."""
        api = _make_api(state='OPEN')
        api.sids = {'sid1': 'user1'}

        mock_req = MagicMock()
        mock_req.sid = 'sid1'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_disconnect()

        assert api.state == SocketState.LIVE

    def test_disconnect_does_not_call_disconnect_peer(self):
        """Transient socket disconnections should NOT tear down the peer
        session.  Only the explicit REST /disconnect_peer endpoint should."""
        api = _make_api(state='OPEN')
        api.sids = {'sid1': 'user1', 'sid2': 'user2'}

        mock_req = MagicMock()
        mock_req.sid = 'sid1'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_disconnect()

        api.server.disconnect_peer.assert_not_called()

    def test_user_slot_cleared_on_disconnect(self):
        """When a user disconnects, their slot in self.users should be
        cleared (set to None) so they can reconnect."""
        api = _make_api(state='OPEN')
        api.users = {'u1': 'sid1', 'u2': 'sid2'}
        api.sids = {'sid1': 'u1', 'sid2': 'u2'}

        mock_req = MagicMock()
        mock_req.sid = 'sid1'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_disconnect()

        assert api.users['u1'] is None
        assert api.users['u2'] == 'sid2'


class TestSocketAPIRun:
    def test_run_when_new_raises(self):
        api = _make_api(state='NEW')
        with patch('socket_api.generate_flask_namespace', return_value={}):
            with pytest.raises(ServerError, match="Cannot start API before initialization"):
                api._run()

    def test_run_when_already_live_raises(self):
        api = _make_api(state='LIVE')
        with patch('socket_api.generate_flask_namespace', return_value={}):
            with pytest.raises(ServerError, match="Cannot start API"):
                api._run()


class TestSocketAPIKill:
    def test_kill_stops_socketio(self):
        api = _make_api(state='LIVE')
        api.socketio = MagicMock()
        api.kill()
        api.socketio.stop.assert_called_once()
        assert api.state == SocketState.INIT

    def test_kill_when_not_live_raises(self):
        api = _make_api(state='INIT')
        with pytest.raises(ServerError):
            api.kill()
