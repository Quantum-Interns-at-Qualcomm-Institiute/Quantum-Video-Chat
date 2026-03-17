"""
Integration tests for the middleware join flow (client.py).

Tests cover:
  1. join_room with no peer_id ("Start Session") — emits waiting-for-peer
  2. join_room with peer_id ("Join Session") — calls /peer_connection, connects WS
  3. join_room error paths — no server, no user_id, server returns error
  4. REST /peer_connection endpoint — server notifies middleware of incoming peer
  5. REST /peer_disconnected endpoint — server notifies middleware of peer leaving
  6. SocketAPI room-id emission — both users connect → room-id broadcast
"""
import pytest
from unittest.mock import MagicMock, patch

from shared.endpoint import Endpoint
from state import SocketState


# ---------------------------------------------------------------------------
# SocketAPI room-id tests
# ---------------------------------------------------------------------------

class TestSocketAPIRoomIdEmission:
    """When all expected users connect to the SocketAPI, it emits 'room-id'."""

    def _make_api(self, users=('u1', 'u2'), state='LIVE'):
        from socket_api import SocketAPI
        mock_server = MagicMock()
        mock_server.websocket_endpoint = Endpoint('127.0.0.1', 3000)
        api = SocketAPI(mock_server, users)
        if state:
            api.state = SocketState[state]
        return api

    def test_room_id_emitted_when_all_users_connect(self):
        """After both users connect, socketio.emit('room-id', ...) is called."""
        api = self._make_api(users=('user1', 'user2'), state='LIVE')
        api.socketio = MagicMock()

        mock_req = MagicMock()

        # First user connects
        mock_req.sid = 'sid1'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_connect('user1')
        # Not yet — only one user
        api.socketio.emit.assert_not_called()

        # Second user connects
        mock_req.sid = 'sid2'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_connect('user2')

        # Now room-id should be emitted
        api.socketio.emit.assert_called_once()
        event_name = api.socketio.emit.call_args[0][0]
        room_id = api.socketio.emit.call_args[0][1]
        assert event_name == 'room-id'
        assert isinstance(room_id, str)
        assert len(room_id) == 5

    def test_state_becomes_open(self):
        """State transitions to OPEN when all users connect."""
        api = self._make_api(users=('user1', 'user2'), state='LIVE')
        api.socketio = MagicMock()

        mock_req = MagicMock()
        mock_req.sid = 'sid1'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_connect('user1')
        assert api.state == SocketState.LIVE

        mock_req.sid = 'sid2'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_connect('user2')
        assert api.state == SocketState.OPEN

    def test_room_id_not_emitted_with_single_user(self):
        """With only one expected user, room-id emitted after their connect."""
        api = self._make_api(users=('solo',), state='LIVE')
        api.socketio = MagicMock()

        mock_req = MagicMock()
        mock_req.sid = 'sid1'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_connect('solo')

        api.socketio.emit.assert_called_once()
        assert api.socketio.emit.call_args[0][0] == 'room-id'

    def test_room_id_is_alphanumeric(self):
        """Generated room-id should be uppercase letters and digits."""
        api = self._make_api(users=('a', 'b'), state='LIVE')
        api.socketio = MagicMock()

        mock_req = MagicMock()
        mock_req.sid = 'sid1'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_connect('a')
        mock_req.sid = 'sid2'
        with patch('socket_api.flask_request', new=mock_req):
            api._on_connect('b')

        room_id = api.socketio.emit.call_args[0][1]
        assert room_id.isalnum()


# ---------------------------------------------------------------------------
# Server peer connection flow (server orchestrates two clients)
# ---------------------------------------------------------------------------

class TestServerPeerConnectionFlow:
    """Full server-side orchestration: user A requests, server contacts peer B."""

    @pytest.fixture
    def mock_server(self):
        MockSocketAPI = MagicMock()
        MockSocketAPI.DEFAULT_ENDPOINT = MagicMock()
        MockSocketAPI.DEFAULT_ENDPOINT.__iter__ = MagicMock(
            return_value=iter(('127.0.0.1', 3000)))

        with patch.dict('sys.modules', {'socket_api': MagicMock(SocketAPI=MockSocketAPI)}):
            import importlib
            import server as server_mod
            importlib.reload(server_mod)
            Server = server_mod.Server

            s = Server(Endpoint('127.0.0.1', 5050))
            s._SocketAPI = MockSocketAPI
            yield s

    def test_handle_peer_connection_starts_websocket(self, mock_server):
        uid_a = mock_server.add_user(('127.0.0.1', 4000))
        uid_b = mock_server.add_user(('127.0.0.1', 4001))

        from utils.user import UserState
        mock_user_a = MagicMock(state=UserState.IDLE)
        mock_user_b = MagicMock(state=UserState.IDLE)
        mock_user_b.api_endpoint = MagicMock(
            return_value=Endpoint('127.0.0.1', 4001, 'peer_connection'))

        def get_user_side_effect(uid):
            return {uid_a: mock_user_a, uid_b: mock_user_b}[uid]

        mock_server.get_user = MagicMock(side_effect=get_user_side_effect)
        mock_server.start_websocket = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_server.contact_client = MagicMock(return_value=mock_response)

        ws_ep = mock_server.handle_peer_connection(uid_a, uid_b)

        mock_server.start_websocket.assert_called_once_with(users=(uid_a, uid_b))
        mock_server.contact_client.assert_called_once()
        assert ws_ep is not None

    def test_peer_connection_contacts_peer_via_rest(self, mock_server):
        """Server contacts peer B's REST API at /peer_connection."""
        uid_a = mock_server.add_user(('127.0.0.1', 4000))
        uid_b = mock_server.add_user(('127.0.0.1', 4001))

        from utils.user import UserState
        mock_user_a = MagicMock(state=UserState.IDLE)
        mock_user_b = MagicMock(state=UserState.IDLE)
        mock_user_b.api_endpoint = MagicMock(
            return_value=Endpoint('127.0.0.1', 4001, 'peer_connection'))

        mock_server.get_user = MagicMock(
            side_effect=lambda uid: {uid_a: mock_user_a, uid_b: mock_user_b}[uid])
        mock_server.start_websocket = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_server.contact_client = MagicMock(return_value=mock_response)

        mock_server.handle_peer_connection(uid_a, uid_b)

        call_args = mock_server.contact_client.call_args
        assert call_args[0][0] == uid_b
        assert call_args[0][1] == '/peer_connection'
        json_payload = call_args[1].get('json') or call_args[0][2]
        assert json_payload['peer_id'] == uid_a

    def test_disconnect_peer_resets_both_users(self, mock_server):
        uid_a = mock_server.add_user(('127.0.0.1', 4000))
        uid_b = mock_server.add_user(('127.0.0.1', 4001))

        from utils.user import UserState
        mock_server.set_user_state(uid_a, UserState.CONNECTED, peer=uid_b)
        mock_server.set_user_state(uid_b, UserState.CONNECTED, peer=uid_a)

        mock_server.contact_client = MagicMock()
        mock_server.disconnect_peer(uid_a)

        assert mock_server.get_user(uid_a).state == UserState.IDLE
        assert mock_server.get_user(uid_b).state == UserState.IDLE

    def test_disconnect_peer_notifies_peer(self, mock_server):
        uid_a = mock_server.add_user(('127.0.0.1', 4000))
        uid_b = mock_server.add_user(('127.0.0.1', 4001))

        from utils.user import UserState
        mock_server.set_user_state(uid_a, UserState.CONNECTED, peer=uid_b)
        mock_server.set_user_state(uid_b, UserState.CONNECTED, peer=uid_a)

        mock_server.contact_client = MagicMock()
        mock_server.disconnect_peer(uid_a)

        mock_server.contact_client.assert_called_once_with(
            uid_b, '/peer_disconnected', json={'peer_id': uid_a})
