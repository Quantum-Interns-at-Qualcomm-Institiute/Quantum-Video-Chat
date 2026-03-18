"""Tests for middleware/client/client.py — Client class."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from shared.endpoint import Endpoint
from shared.state import ClientState
from shared.exceptions import InternalClientError


class TestClient:
    @pytest.fixture
    def client_instance(self, mock_adapter):
        """Create a Client with mocked dependencies to avoid actual connections."""
        with patch('client.client.ClientAPI') as MockAPI, \
             patch('client.client.SocketClient') as MockSocket, \
             patch.object(
                 # Prevent connect() from actually running in __init__
                 __import__('client.server_comms', fromlist=['ServerCommsMixin']).ServerCommsMixin,
                 'connect', return_value=True):

            MockAPI.init.return_value = MagicMock()

            from client.client import Client
            c = Client(
                adapter=mock_adapter,
                server_endpoint=Endpoint('127.0.0.1', 5050),
                api_endpoint=Endpoint('127.0.0.1', 4000),
            )
            c._MockAPI = MockAPI
            c._MockSocket = MockSocket
            yield c

    def test_initial_state(self, mock_adapter):
        """Verify that state starts as LIVE after __init__ calls connect()."""
        with patch('client.client.ClientAPI') as MockAPI, \
             patch('client.client.SocketClient'), \
             patch('client.server_comms.requests.post') as mock_post:

            MockAPI.init.return_value = MagicMock()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'user_id': 'test1'}
            mock_post.return_value = mock_response

            from client.client import Client
            c = Client(
                adapter=mock_adapter,
                server_endpoint=Endpoint('127.0.0.1', 5050),
                api_endpoint=Endpoint('127.0.0.1', 4000),
            )
            assert c.state == ClientState.LIVE

    def test_set_server_endpoint_when_live_raises(self, client_instance):
        client_instance.state = ClientState.LIVE
        with pytest.raises(InternalClientError):
            client_instance.set_server_endpoint(Endpoint('10.0.0.1', 9000))

    def test_set_server_endpoint_when_new(self, client_instance):
        client_instance.state = ClientState.NEW
        client_instance.set_server_endpoint(Endpoint('10.0.0.1', 9000))
        assert client_instance.server_endpoint.ip == '10.0.0.1'

    def test_set_api_endpoint_when_live_raises(self, client_instance):
        client_instance.state = ClientState.LIVE
        with pytest.raises(InternalClientError):
            client_instance.set_api_endpoint(Endpoint('10.0.0.1', 9000))

    def test_handle_peer_connection_when_connected_raises(self, client_instance):
        client_instance.state = ClientState.CONNECTED
        with pytest.raises(InternalClientError):
            client_instance.handle_peer_connection('peer1', ('127.0.0.1', 3000))

    def test_handle_peer_connection_success(self, client_instance):
        client_instance.state = ClientState.LIVE
        with patch.object(client_instance, 'connect_to_websocket'):
            result = client_instance.handle_peer_connection('peer1', ('127.0.0.1', 3000))
            assert result is True

    def test_handle_peer_connection_passes_session_settings(self, client_instance):
        """session_settings from the host must be forwarded to connect_to_websocket."""
        client_instance.state = ClientState.LIVE
        settings = {'video_width': 320, 'frame_rate': 30}
        with patch.object(client_instance, 'connect_to_websocket') as mock_ws:
            client_instance.handle_peer_connection(
                'peer1', ('127.0.0.1', 3000), session_settings=settings)
            mock_ws.assert_called_once()
            _, kwargs = mock_ws.call_args
            assert kwargs.get('session_settings') == settings

    def test_handle_peer_connection_failure(self, client_instance):
        client_instance.state = ClientState.LIVE
        with patch.object(client_instance, 'connect_to_websocket',
                         side_effect=Exception("connection failed")), \
             patch('client.client.logger'):  # silence logger.error bug (2 string args)
            result = client_instance.handle_peer_connection('peer1', ('127.0.0.1', 3000))
            assert result is False

    def test_kill_calls_cleanup(self, client_instance):
        with patch.object(client_instance, 'disconnect_from_server'):
            client_instance.api_instance = MagicMock()
            client_instance.websocket_instance = MagicMock()
            client_instance.kill()
            client_instance.disconnect_from_server.assert_called_once()
            client_instance.api_instance.kill.assert_called_once()
            client_instance.websocket_instance.kill.assert_called_once()

    def test_display_message(self, client_instance, capsys):
        client_instance.display_message('user1', 'hello')
        captured = capsys.readouterr()
        assert '(user1): hello' in captured.out

    def test_kill_suppresses_api_exception(self, client_instance):
        """kill() should not raise even if api_instance.kill() throws."""
        with patch.object(client_instance, 'disconnect_from_server'):
            mock_api = MagicMock()
            mock_api.kill.side_effect = Exception("api crash")
            client_instance.api_instance = mock_api
            client_instance.websocket_instance = None
            # Should not raise
            client_instance.kill()

    def test_kill_suppresses_socket_exception(self, client_instance):
        """kill() should not raise even if websocket_instance.kill() throws."""
        with patch.object(client_instance, 'disconnect_from_server'):
            client_instance.api_instance = MagicMock()
            mock_ws = MagicMock()
            mock_ws.kill.side_effect = Exception("socket crash")
            client_instance.websocket_instance = mock_ws
            # Should not raise
            client_instance.kill()

    def test_connect_to_websocket_failure_raises(self, client_instance):
        """connect_to_websocket should re-raise exceptions from SocketClient."""
        with patch('client.client.SocketClient') as MockSocket:
            mock_instance = MagicMock()
            mock_instance.start.side_effect = Exception("ws error")
            MockSocket.return_value = mock_instance
            with pytest.raises(Exception, match="ws error"):
                client_instance.connect_to_websocket(('127.0.0.1', 3000))

    def test_connect_to_websocket_passes_session_settings(self, client_instance):
        """connect_to_websocket should forward session_settings to SocketClient()."""
        with patch('client.client.SocketClient') as MockSocket:
            MockSocket.return_value = MagicMock()
            settings = {'frame_rate': 30}
            client_instance.connect_to_websocket(
                ('127.0.0.1', 3000), session_settings=settings)
            call_kwargs = MockSocket.call_args[1]
            assert call_kwargs.get('session_settings') == settings


class TestDisconnectFromPeer:
    """Tests for disconnect_from_peer() and handle_peer_disconnected()."""

    @pytest.fixture
    def client_instance(self, mock_adapter):
        with patch('client.client.ClientAPI') as MockAPI, \
             patch('client.client.SocketClient'), \
             patch.object(
                 __import__('client.server_comms', fromlist=['ServerCommsMixin']).ServerCommsMixin,
                 'connect', return_value=True):

            MockAPI.init.return_value = MagicMock()

            from client.client import Client
            c = Client(
                adapter=mock_adapter,
                server_endpoint=Endpoint('127.0.0.1', 5050),
                api_endpoint=Endpoint('127.0.0.1', 4000),
            )
            # Set up a mock websocket instance
            mock_ws = MagicMock()
            mock_ws.is_connected.return_value = True
            mock_ws.av = MagicMock()
            mock_ws.av._key_stop = MagicMock()
            c.websocket_instance = mock_ws
            c._mock_ws = mock_ws
            yield c

    def test_disconnect_from_peer_resets_state_to_live(self, client_instance):
        client_instance.state = ClientState.CONNECTED
        with patch.object(client_instance, 'contact_server'):
            client_instance.disconnect_from_peer()
        assert client_instance.state == ClientState.LIVE

    def test_disconnect_from_peer_stops_key_rotation(self, client_instance):
        client_instance.state = ClientState.CONNECTED
        with patch.object(client_instance, 'contact_server'):
            client_instance.disconnect_from_peer()
        client_instance._mock_ws.av._key_stop.set.assert_called_once()

    def test_disconnect_from_peer_disconnects_socket(self, client_instance):
        client_instance.state = ClientState.CONNECTED
        with patch.object(client_instance, 'contact_server'):
            client_instance.disconnect_from_peer()
        client_instance._mock_ws.disconnect.assert_called_once()

    def test_disconnect_from_peer_notifies_server(self, client_instance):
        client_instance.state = ClientState.CONNECTED
        client_instance.user_id = 'test_user'
        with patch.object(client_instance, 'contact_server') as mock_contact:
            client_instance.disconnect_from_peer()
        mock_contact.assert_called_once_with(
            '/disconnect_peer', json={'user_id': 'test_user'})

    def test_disconnect_from_peer_emits_status(self, client_instance, mock_adapter):
        client_instance.state = ClientState.CONNECTED
        with patch.object(client_instance, 'contact_server'):
            client_instance.disconnect_from_peer()
        event_names = [e for e, _ in mock_adapter.status_events]
        assert 'peer_disconnected' in event_names

    def test_disconnect_from_peer_ignores_when_not_connected(self, client_instance, mock_adapter):
        client_instance.state = ClientState.LIVE
        client_instance.disconnect_from_peer()
        assert client_instance.state == ClientState.LIVE
        # No status event should have been emitted
        event_names = [e for e, _ in mock_adapter.status_events]
        assert 'peer_disconnected' not in event_names

    def test_handle_peer_disconnected_resets_state(self, client_instance, mock_adapter):
        client_instance.state = ClientState.CONNECTED
        client_instance.handle_peer_disconnected('alice')
        assert client_instance.state == ClientState.LIVE

    def test_handle_peer_disconnected_emits_status_with_peer_id(self, client_instance, mock_adapter):
        client_instance.state = ClientState.CONNECTED
        client_instance.handle_peer_disconnected('alice')
        events = {e: d for e, d in mock_adapter.status_events}
        assert 'peer_disconnected' in events
        assert events['peer_disconnected'].get('peer_id') == 'alice'

    def test_handle_peer_disconnected_ignores_when_not_connected(self, client_instance, mock_adapter):
        """handle_peer_disconnected is a no-op when not in CONNECTED state."""
        client_instance.state = ClientState.LIVE
        client_instance.handle_peer_disconnected('alice')
        assert client_instance.state == ClientState.LIVE
        event_names = [e for e, _ in mock_adapter.status_events]
        assert 'peer_disconnected' not in event_names

    def test_handle_peer_connection_sets_connected_state(self, client_instance):
        """handle_peer_connection sets state to CONNECTED on success."""
        client_instance.state = ClientState.LIVE
        with patch.object(client_instance, 'connect_to_websocket'):
            client_instance.handle_peer_connection('peer1', ('127.0.0.1', 3000))
        assert client_instance.state == ClientState.CONNECTED


class TestHandlePeerConnectionStatusEvents:
    """handle_peer_connection() emits the right status events on incoming calls."""

    @pytest.fixture
    def client_instance(self, mock_adapter):
        with patch('client.client.ClientAPI') as MockAPI, \
             patch('client.client.SocketClient'), \
             patch.object(
                 __import__('client.server_comms', fromlist=['ServerCommsMixin']).ServerCommsMixin,
                 'connect', return_value=True):

            MockAPI.init.return_value = MagicMock()

            from client.client import Client
            c = Client(
                adapter=mock_adapter,
                server_endpoint=Endpoint('127.0.0.1', 5050),
                api_endpoint=Endpoint('127.0.0.1', 4000),
            )
            yield c

    def test_peer_incoming_emitted_with_peer_id(self, client_instance, mock_adapter):
        client_instance.state = ClientState.LIVE
        with patch.object(client_instance, 'connect_to_websocket'):
            client_instance.handle_peer_connection('alice', ('127.0.0.1', 3000))

        events = {e: d for e, d in mock_adapter.status_events}
        assert 'peer_incoming' in events
        assert events['peer_incoming'].get('peer_id') == 'alice'

    def test_peer_connected_emitted_on_success(self, client_instance, mock_adapter):
        client_instance.state = ClientState.LIVE
        with patch.object(client_instance, 'connect_to_websocket'):
            client_instance.handle_peer_connection('alice', ('127.0.0.1', 3000))

        event_names = [e for e, _ in mock_adapter.status_events]
        assert 'peer_connected' in event_names

    def test_peer_incoming_before_peer_connected(self, client_instance, mock_adapter):
        client_instance.state = ClientState.LIVE
        with patch.object(client_instance, 'connect_to_websocket'):
            client_instance.handle_peer_connection('alice', ('127.0.0.1', 3000))

        event_names = [e for e, _ in mock_adapter.status_events]
        assert event_names.index('peer_incoming') < event_names.index('peer_connected')

    def test_peer_connected_not_emitted_on_failure(self, client_instance, mock_adapter):
        client_instance.state = ClientState.LIVE
        with patch.object(client_instance, 'connect_to_websocket',
                          side_effect=Exception("ws error")), \
             patch('client.client.logger'):
            client_instance.handle_peer_connection('alice', ('127.0.0.1', 3000))

        event_names = [e for e, _ in mock_adapter.status_events]
        assert 'peer_connected' not in event_names
        # peer_incoming was still emitted — we knew a request arrived
        assert 'peer_incoming' in event_names
