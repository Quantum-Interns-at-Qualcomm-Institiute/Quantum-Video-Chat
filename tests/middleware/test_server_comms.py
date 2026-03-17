"""Tests for middleware/client/server_comms.py — ServerCommsMixin."""
import pytest
from unittest.mock import MagicMock, patch, call
from shared.endpoint import Endpoint
from shared.state import ClientState
from shared.exceptions import (
    ConnectionRefused, UnexpectedResponse, InternalClientError,
)
from client.server_comms import ServerCommsMixin


class ConcreteClient(ServerCommsMixin):
    """Minimal host class for ServerCommsMixin testing."""
    def __init__(self):
        self.server_endpoint = Endpoint('127.0.0.1', 5050)
        self.api_endpoint = Endpoint('127.0.0.1', 4000)
        self.state = ClientState.NEW
        self.user_id = None
        self.websocket_connected = False
        self.adapter = MagicMock()  # absorb send_status calls

    def connect_to_websocket(self, endpoint):
        self.websocket_connected = True


class TestContactServer:
    @patch('client.server_comms.requests.post')
    def test_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = ConcreteClient()
        response = client.contact_server('/test', json={'key': 'val'})
        assert response.status_code == 200

    @patch('client.server_comms.requests.post')
    def test_connection_error_raises(self, mock_post):
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("refused")

        client = ConcreteClient()
        with pytest.raises(ConnectionRefused):
            client.contact_server('/test')

    @patch('client.server_comms.requests.post')
    def test_non_200_with_json_details(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'details': 'bad param'}
        mock_response.reason = 'Bad Request'
        mock_post.return_value = mock_response

        client = ConcreteClient()
        with pytest.raises(UnexpectedResponse):
            client.contact_server('/test')

    @patch('client.server_comms.requests.post')
    def test_non_200_without_json(self, mock_post):
        import requests as req
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = req.exceptions.JSONDecodeError("", "", 0)
        mock_response.reason = 'Internal Server Error'
        mock_post.return_value = mock_response

        client = ConcreteClient()
        with pytest.raises(UnexpectedResponse, match="Internal Server Error"):
            client.contact_server('/test')


class TestConnect:
    @patch('client.server_comms.requests.post')
    def test_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'user_id': 'abc12'}
        mock_post.return_value = mock_response

        client = ConcreteClient()
        result = client.connect(max_retries=0)
        assert result is True
        assert client.user_id == 'abc12'
        assert client.state == ClientState.LIVE

    @patch('client.server_comms.requests.post')
    def test_already_live_raises(self, mock_post):
        client = ConcreteClient()
        client.state = ClientState.LIVE

        with pytest.raises(InternalClientError):
            client.connect(max_retries=0)

    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_connection_refused_returns_false(self, mock_post, mock_sleep):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("refused")

        client = ConcreteClient()
        result = client.connect(max_retries=0)
        assert result is False


class TestConnectToPeer:
    @patch('client.server_comms.requests.post')
    def test_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'socket_endpoint': ('127.0.0.1', 3000)}
        mock_post.return_value = mock_response

        client = ConcreteClient()
        client.user_id = 'test_user'
        client.connect_to_peer('peer123')
        assert client.websocket_connected is True

    @patch('client.server_comms.requests.post')
    def test_includes_session_settings(self, mock_post):
        """connect_to_peer must include session_settings in the POST body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'socket_endpoint': ('127.0.0.1', 3000)}
        mock_post.return_value = mock_response

        client = ConcreteClient()
        client.user_id = 'test_user'
        client.connect_to_peer('peer123')

        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs['json']
        assert 'session_settings' in payload
        ss = payload['session_settings']
        for key in ('video_width', 'video_height', 'frame_rate',
                    'sample_rate', 'audio_wait', 'key_length',
                    'encrypt_scheme', 'key_generator'):
            assert key in ss, f"session_settings missing '{key}'"


# ---------------------------------------------------------------------------
# Status event tests
# ---------------------------------------------------------------------------

class TestConnectStatusEvents:
    """connect() emits the right adapter status events at each outcome."""

    @patch('client.server_comms.requests.post')
    def test_server_connecting_emitted_before_contact(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'user_id': 'u1'}
        mock_post.return_value = mock_response

        client = ConcreteClient()
        client.connect(max_retries=0)

        events = [c.args[0] for c in client.adapter.send_status.call_args_list]
        assert 'server_connecting' in events
        # Must be the first status event
        first_call = client.adapter.send_status.call_args_list[0]
        assert first_call.args[0] == 'server_connecting'

    @patch('client.server_comms.requests.post')
    def test_server_connected_emitted_on_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'user_id': 'u1'}
        mock_post.return_value = mock_response

        client = ConcreteClient()
        client.connect(max_retries=0)

        # Last call should be server_connected with the user_id
        last_call = client.adapter.send_status.call_args_list[-1]
        assert last_call.args[0] == 'server_connected'
        assert 'user_id' in last_call.args[1]

    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_server_error_emitted_on_connection_refused(self, mock_post, mock_sleep):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("refused")

        client = ConcreteClient()
        client.connect(max_retries=0)

        events = [c.args[0] for c in client.adapter.send_status.call_args_list]
        assert 'server_error' in events
        # server_connected must NOT appear
        assert 'server_connected' not in events

    @patch('client.server_comms.requests.post')
    def test_connecting_then_connected_ordering(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'user_id': 'u2'}
        mock_post.return_value = mock_response

        client = ConcreteClient()
        client.connect(max_retries=0)

        events = [c.args[0] for c in client.adapter.send_status.call_args_list]
        assert events.index('server_connecting') < events.index('server_connected')


class TestConnectToPeerStatusEvents:
    """connect_to_peer() emits peer_outgoing before contact and peer_connected after WebSocket."""

    @patch('client.server_comms.requests.post')
    def test_peer_outgoing_emitted_with_peer_id(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'socket_endpoint': ('127.0.0.1', 3000)}
        mock_post.return_value = mock_response

        client = ConcreteClient()
        client.user_id = 'me'
        client.connect_to_peer('peer42')

        client.adapter.send_status.assert_any_call('peer_outgoing', {'peer_id': 'peer42'})

    @patch('client.server_comms.requests.post')
    def test_peer_connected_emitted_after_websocket(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'socket_endpoint': ('127.0.0.1', 3000)}
        mock_post.return_value = mock_response

        client = ConcreteClient()
        client.user_id = 'me'
        client.connect_to_peer('peer42')

        events = [c.args[0] for c in client.adapter.send_status.call_args_list]
        assert 'peer_connected' in events
        # peer_outgoing must come before peer_connected
        assert events.index('peer_outgoing') < events.index('peer_connected')

    @patch('client.server_comms.requests.post')
    def test_outgoing_emitted_before_post(self, mock_post):
        """peer_outgoing must fire before the network call, not after."""
        call_order = []
        def track_post(*args, **kwargs):
            call_order.append('post')
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {'socket_endpoint': ('127.0.0.1', 3000)}
            return r
        mock_post.side_effect = track_post

        client = ConcreteClient()
        original_send = client.adapter.send_status
        def track_status(event, data=None):
            call_order.append(event)
            return original_send(event, data)
        client.adapter.send_status = track_status

        client.user_id = 'me'
        client.connect_to_peer('peer42')

        assert call_order.index('peer_outgoing') < call_order.index('post')


class TestDisconnectFromServer:
    """Tests for disconnect_from_server()."""

    @patch('client.server_comms.requests.post')
    def test_sends_remove_user_to_server(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        client = ConcreteClient()
        client.state = ClientState.LIVE
        client.user_id = 'abc12'
        client.disconnect_from_server()
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert '/remove_user' in str(call_kwargs)

    @patch('client.server_comms.requests.post')
    def test_resets_state_to_init(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        client = ConcreteClient()
        client.state = ClientState.LIVE
        client.user_id = 'abc12'
        client.disconnect_from_server()
        assert client.state == ClientState.INIT

    def test_noop_when_not_connected(self):
        client = ConcreteClient()
        client.state = ClientState.NEW
        client.disconnect_from_server()
        assert client.state == ClientState.NEW

    @patch('client.server_comms.requests.post')
    def test_swallows_connection_error(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("refused")
        client = ConcreteClient()
        client.state = ClientState.LIVE
        client.user_id = 'abc12'
        # Should not raise
        client.disconnect_from_server()
        assert client.state == ClientState.INIT
