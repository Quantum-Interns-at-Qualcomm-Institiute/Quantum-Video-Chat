"""Tests for server/server.py — Server class."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from shared.endpoint import Endpoint
from shared.exceptions import ServerError, BadGateway, BadRequest


class TestServer:
    def test_add_user(self, mock_server):
        uid = mock_server.add_user(('127.0.0.1', 4000))
        assert isinstance(uid, str)
        assert len(uid) == 5

    def test_get_user_returns_user(self, mock_server):
        """add_user now stores a proper User; get_user should return it without error."""
        from utils.user import User
        uid = mock_server.add_user(('127.0.0.1', 4000))
        user = mock_server.get_user(uid)
        assert isinstance(user, User)
        assert user.api_endpoint.ip == '127.0.0.1'

    def test_remove_user_nonexistent_silently(self, mock_server):
        """UserManager.remove_user swallows UserNotFound (doesn't re-raise),
        but Server.remove_user wraps it and DOES re-raise."""
        # The server.remove_user calls user_manager.remove_user which catches
        # UserNotFound and doesn't re-raise. But server.remove_user also catches
        # it from user_manager and re-raises. Since user_manager doesn't re-raise,
        # server.remove_user logs success silently.
        mock_server.remove_user('nonexistent')  # should not raise

    def test_handle_peer_connection_self(self, mock_server):
        with pytest.raises(BadRequest, match="self"):
            mock_server.handle_peer_connection('user1', 'user1')

    def test_handle_peer_connection_user_not_found(self, mock_server):
        """Looking up a non-existent user raises BadRequest."""
        with pytest.raises(BadRequest):
            mock_server.handle_peer_connection('user1', 'user2')

    def test_handle_peer_connection_peer_not_found(self, mock_server):
        """When the user exists but the peer doesn't, BadRequest is raised."""
        uid = mock_server.add_user(('127.0.0.1', 4000))
        with pytest.raises(BadRequest):
            mock_server.handle_peer_connection(uid, 'nonexistent')

    @patch('requests.post')
    def test_contact_client(self, mock_post, mock_server):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        mock_user = MagicMock()
        mock_user.api_endpoint = MagicMock(return_value=Endpoint('127.0.0.1', 4000, 'test'))
        mock_user.api_endpoint.__str__ = lambda self: 'http://127.0.0.1:4000/test'

        mock_server.get_user = MagicMock(return_value=mock_user)
        response = mock_server.contact_client('uid', '/test', json={'key': 'val'})
        assert response.status_code == 200
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_contact_client_failure(self, mock_post, mock_server):
        mock_post.side_effect = ConnectionError("refused")

        mock_user = MagicMock()
        mock_user.api_endpoint = MagicMock(return_value=Endpoint('127.0.0.1', 4000))
        mock_server.get_user = MagicMock(return_value=mock_user)

        with pytest.raises(ConnectionError):
            mock_server.contact_client('uid', '/test', json={})

    def test_set_websocket_endpoint(self, mock_server):
        ep = Endpoint('10.0.0.1', 9000)
        mock_server.set_websocket_endpoint(ep)
        assert mock_server.websocket_endpoint.ip == '10.0.0.1'
        assert mock_server.websocket_endpoint.port == 9000

    def test_start_websocket(self, mock_server):
        mock_instance = MagicMock()
        mock_server._SocketAPI.return_value = mock_instance

        mock_server.start_websocket(users=('u1', 'u2'))
        mock_server._SocketAPI.assert_called_once()
        mock_instance.start.assert_called_once()

    def test_disconnect_peer_resets_both_users(self, mock_server):
        """disconnect_peer sets both user and peer to IDLE."""
        from utils.user import UserState

        uid_a = mock_server.add_user(('127.0.0.1', 4000))
        uid_b = mock_server.add_user(('127.0.0.1', 4001))

        mock_server.set_user_state(uid_a, UserState.CONNECTED, peer=uid_b)
        mock_server.set_user_state(uid_b, UserState.CONNECTED, peer=uid_a)

        mock_server.contact_client = MagicMock()
        mock_server.disconnect_peer(uid_a)

        user_a = mock_server.get_user(uid_a)
        user_b = mock_server.get_user(uid_b)
        assert user_a.state == UserState.IDLE
        assert user_b.state == UserState.IDLE

    def test_disconnect_peer_contacts_peer_api(self, mock_server):
        """disconnect_peer sends POST /peer_disconnected to the peer."""
        from utils.user import UserState

        uid_a = mock_server.add_user(('127.0.0.1', 4000))
        uid_b = mock_server.add_user(('127.0.0.1', 4001))
        mock_server.set_user_state(uid_a, UserState.CONNECTED, peer=uid_b)
        mock_server.set_user_state(uid_b, UserState.CONNECTED, peer=uid_a)

        mock_server.contact_client = MagicMock()
        mock_server.disconnect_peer(uid_a)

        mock_server.contact_client.assert_called_once_with(
            uid_b, '/peer_disconnected', json={'peer_id': uid_a})

    def test_disconnect_peer_unknown_user_raises(self, mock_server):
        """disconnect_peer raises BadRequest for unknown user."""
        with pytest.raises(BadRequest):
            mock_server.disconnect_peer('nonexistent')

    def test_disconnect_peer_no_peer_noop(self, mock_server):
        """disconnect_peer with no active peer is a no-op."""
        uid = mock_server.add_user(('127.0.0.1', 4000))
        mock_server.disconnect_peer(uid)  # should not raise

    def test_handle_peer_connection_full_success(self, mock_server):
        """Test the full happy path with mocked get_user."""
        from utils.user import User, UserState

        user_ep = Endpoint('127.0.0.1', 4000)
        peer_ep = Endpoint('127.0.0.1', 4001)
        mock_user = MagicMock(state=UserState.IDLE, api_endpoint=user_ep)
        mock_peer = MagicMock(state=UserState.IDLE, api_endpoint=peer_ep)
        mock_peer.api_endpoint = MagicMock(return_value=Endpoint('127.0.0.1', 4001, 'peer_connection'))

        def side_effect(uid):
            return {'u1': mock_user, 'u2': mock_peer}[uid]

        mock_server.get_user = MagicMock(side_effect=side_effect)
        mock_server.start_websocket = MagicMock()
        mock_server.set_user_state = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_server.contact_client = MagicMock(return_value=mock_response)

        result = mock_server.handle_peer_connection('u1', 'u2')
        assert result is not None
        mock_server.start_websocket.assert_called_once()
        mock_server.contact_client.assert_called_once()
        # Verify both users were set to CONNECTED
        assert mock_server.set_user_state.call_count == 2

    def test_handle_peer_connection_forwards_session_settings(self, mock_server):
        """session_settings from the host must be included in the peer contact payload."""
        from utils.user import User, UserState

        mock_user = MagicMock(state=UserState.IDLE, api_endpoint=Endpoint('127.0.0.1', 4000))
        mock_peer = MagicMock(state=UserState.IDLE, api_endpoint=Endpoint('127.0.0.1', 4001))
        mock_peer.api_endpoint = MagicMock(
            return_value=Endpoint('127.0.0.1', 4001, 'peer_connection'))

        def side_effect(uid):
            return {'u1': mock_user, 'u2': mock_peer}[uid]

        mock_server.get_user = MagicMock(side_effect=side_effect)
        mock_server.start_websocket = MagicMock()
        mock_server.set_user_state = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_server.contact_client = MagicMock(return_value=mock_response)

        settings = {'video_width': 320, 'frame_rate': 30}
        mock_server.handle_peer_connection('u1', 'u2', session_settings=settings)

        call_kwargs = mock_server.contact_client.call_args[1]
        assert call_kwargs['json']['session_settings'] == settings
