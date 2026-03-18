"""
Integration-style unit tests for the client ↔ server ↔ client connection flow.

These tests exercise the real business logic across class boundaries while
mocking network I/O (HTTP requests, WebSocket connections, Flask threads).

Four scenarios are covered:
  1. A single client connecting to a server
  2. Two clients connecting to the same server
  3. Two clients connecting to each other through the server
  4. A connected client disconnecting from a peer

NOTE: These tests depend on the old middleware architecture (client.client,
ClientAPI, SocketClient) which was replaced by the new Socket.IO-based
middleware in the consolidation. They need to be rewritten for the new
architecture.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Tests depend on old middleware architecture (client.client); needs rewrite for new middleware")
from unittest.mock import MagicMock, patch

from shared.endpoint import Endpoint
from shared.state import ClientState
from shared.adapters import FrontendAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockAdapter(FrontendAdapter):
    """Minimal concrete adapter for testing (no real socket)."""

    def __init__(self):
        self.frames = []
        self._callback = None

    def send_frame(self, data: bytes) -> None:
        self.frames.append(data)

    def send_self_frame(self, data: bytes, width: int, height: int) -> None:
        pass

    def on_peer_id(self, callback) -> None:
        self._callback = callback

    def send_status(self, event: str, data: dict = None) -> None:
        pass


@pytest.fixture
def mock_server():
    """Create a Server with SocketAPI mocked out.

    Mirrors the pattern in tests/server/conftest.py — the patch.dict
    context is kept alive for the duration of the test so that the
    reloaded server module's imports remain valid.
    """
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


def make_client(user_id_from_server: str, api_port: int = 4000):
    """Return a Client whose __init__ connect() succeeds with the given user_id.

    ClientAPI.init().start() is mocked (no real Flask thread).
    requests.post is mocked to simulate a successful /create_user response.
    """
    mock_adapter = MockAdapter()

    with patch('client.client.ClientAPI') as MockAPI, \
         patch('client.client.SocketClient'), \
         patch('client.server_comms.requests.post') as mock_post:

        MockAPI.init.return_value = MagicMock()  # thread-like object with .start()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'user_id': user_id_from_server}
        mock_post.return_value = mock_response

        from client.client import Client
        c = Client(
            adapter=mock_adapter,
            server_endpoint=Endpoint('127.0.0.1', 5050),
            api_endpoint=Endpoint('127.0.0.1', api_port),
        )
    return c


# ---------------------------------------------------------------------------
# 1. Single client → server
# ---------------------------------------------------------------------------

class TestSingleClientConnectsToServer:
    """Verify that one client can register with the server and receive a user_id."""

    def test_client_receives_user_id(self, mock_server):
        user_id = mock_server.add_user(('127.0.0.1', 4000))

        client = make_client(user_id_from_server=user_id)
        assert client.user_id is not None
        assert len(client.user_id) == 5

    def test_client_state_becomes_live(self, mock_server):
        user_id = mock_server.add_user(('127.0.0.1', 4000))
        client = make_client(user_id_from_server=user_id)
        assert client.state == ClientState.LIVE

    def test_server_stores_user(self, mock_server):
        user_id = mock_server.add_user(('127.0.0.1', 4000))
        assert mock_server.user_manager.storage.has_user(user_id)


# ---------------------------------------------------------------------------
# 2. Two clients → server
# ---------------------------------------------------------------------------

class TestTwoClientsConnectToServer:
    """Verify that two clients can independently register with the same server."""

    @pytest.fixture
    def server_and_clients(self, mock_server):
        uid_a = mock_server.add_user(('127.0.0.1', 4000))
        uid_b = mock_server.add_user(('127.0.0.1', 4001))

        client_a = make_client(user_id_from_server=uid_a, api_port=4000)
        client_b = make_client(user_id_from_server=uid_b, api_port=4001)
        return mock_server, client_a, client_b, uid_a, uid_b

    def test_two_users_stored(self, server_and_clients):
        server, _, _, uid_a, uid_b = server_and_clients
        assert server.user_manager.storage.has_user(uid_a)
        assert server.user_manager.storage.has_user(uid_b)

    def test_both_clients_live(self, server_and_clients):
        _, client_a, client_b, _, _ = server_and_clients
        assert client_a.state == ClientState.LIVE
        assert client_b.state == ClientState.LIVE

    def test_user_ids_are_unique(self, server_and_clients):
        _, _, _, uid_a, uid_b = server_and_clients
        assert uid_a != uid_b


# ---------------------------------------------------------------------------
# 3. Two clients → each other (through server)
# ---------------------------------------------------------------------------

class TestTwoClientsConnectToEachOther:
    """Verify the full peer-connection handshake orchestrated by the server."""

    @pytest.fixture
    def setup(self, mock_server):
        """Create a server and two live clients with proper User objects."""
        uid_a = mock_server.add_user(('127.0.0.1', 4000))
        uid_b = mock_server.add_user(('127.0.0.1', 4001))

        client_a = make_client(user_id_from_server=uid_a, api_port=4000)
        client_b = make_client(user_id_from_server=uid_b, api_port=4001)

        return mock_server, client_a, client_b, uid_a, uid_b

    def _mock_users_on_server(self, server, uid_a, uid_b):
        """Replace server.get_user to return proper User objects with IDLE state."""
        from utils.user import UserState

        ep_a = Endpoint('127.0.0.1', 4000)
        ep_b = Endpoint('127.0.0.1', 4001)

        mock_user_a = MagicMock(state=UserState.IDLE, api_endpoint=ep_a)
        mock_user_b = MagicMock(state=UserState.IDLE, api_endpoint=ep_b)
        # contact_client calls user.api_endpoint('/peer_connection')
        mock_user_b.api_endpoint = MagicMock(
            return_value=Endpoint('127.0.0.1', 4001, 'peer_connection'))

        def side_effect(uid):
            return {uid_a: mock_user_a, uid_b: mock_user_b}[uid]

        server.get_user = MagicMock(side_effect=side_effect)
        return mock_user_a, mock_user_b

    def test_server_starts_websocket(self, setup):
        server, _, _, uid_a, uid_b = setup
        self._mock_users_on_server(server, uid_a, uid_b)
        server.start_websocket = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        server.contact_client = MagicMock(return_value=mock_response)

        server.handle_peer_connection(uid_a, uid_b)
        server.start_websocket.assert_called_once_with(users=(uid_a, uid_b))

    def test_server_contacts_peer(self, setup):
        server, _, _, uid_a, uid_b = setup
        self._mock_users_on_server(server, uid_a, uid_b)
        server.start_websocket = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        server.contact_client = MagicMock(return_value=mock_response)

        server.handle_peer_connection(uid_a, uid_b)
        server.contact_client.assert_called_once()
        call_args = server.contact_client.call_args
        assert call_args[0][0] == uid_b  # peer_id
        assert call_args[0][1] == '/peer_connection'

    def test_initiator_calls_connect_to_websocket(self, setup):
        """When client_a calls connect_to_peer, it should trigger connect_to_websocket."""
        server, client_a, client_b, uid_a, uid_b = setup

        ws_endpoint = ('127.0.0.1', 3000)
        with patch('client.server_comms.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'socket_endpoint': ws_endpoint}
            mock_post.return_value = mock_response

            with patch.object(client_a, 'connect_to_websocket') as mock_ws:
                client_a.connect_to_peer(uid_b)
                mock_ws.assert_called_once()

    def test_peer_handle_returns_true(self, setup):
        """When the peer receives a connection request, handle_peer_connection returns True."""
        _, _, client_b, _, _ = setup
        client_b.state = ClientState.LIVE

        with patch.object(client_b, 'connect_to_websocket'):
            result = client_b.handle_peer_connection(
                'some_peer', Endpoint('127.0.0.1', 3000))
            assert result is True

    def test_full_flow_end_to_end(self, setup):
        """Test the complete happy path:
        server orchestrates → peer notified → both clients connect to websocket."""
        server, client_a, client_b, uid_a, uid_b = setup
        self._mock_users_on_server(server, uid_a, uid_b)
        server.start_websocket = MagicMock()

        # Server contacts peer → simulate 200
        mock_peer_response = MagicMock()
        mock_peer_response.status_code = 200
        server.contact_client = MagicMock(return_value=mock_peer_response)

        # 1) Server orchestrates the peer connection
        ws_ep = server.handle_peer_connection(uid_a, uid_b)
        assert ws_ep is not None
        server.start_websocket.assert_called_once()
        server.contact_client.assert_called_once()

        # 2) Client A initiates its side
        with patch('client.server_comms.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'socket_endpoint': ('127.0.0.1', 3000)
            }
            mock_post.return_value = mock_response

            with patch.object(client_a, 'connect_to_websocket') as mock_ws_a:
                client_a.connect_to_peer(uid_b)
                mock_ws_a.assert_called_once()

        # 3) Client B handles the incoming request
        client_b.state = ClientState.LIVE
        with patch.object(client_b, 'connect_to_websocket') as mock_ws_b:
            result = client_b.handle_peer_connection(
                uid_a, Endpoint('127.0.0.1', 3000))
            assert result is True
            mock_ws_b.assert_called_once()


# ---------------------------------------------------------------------------
# 4. Disconnect from peer
# ---------------------------------------------------------------------------

class TestDisconnectFromPeer:
    """Verify the disconnect flow across client and server boundaries."""

    @pytest.fixture
    def connected_setup(self, mock_server):
        """Create server + two clients and simulate them being CONNECTED."""
        uid_a = mock_server.add_user(('127.0.0.1', 4000))
        uid_b = mock_server.add_user(('127.0.0.1', 4001))

        client_a = make_client(user_id_from_server=uid_a, api_port=4000)
        client_b = make_client(user_id_from_server=uid_b, api_port=4001)

        from utils.user import UserState
        mock_server.set_user_state(uid_a, UserState.CONNECTED, peer=uid_b)
        mock_server.set_user_state(uid_b, UserState.CONNECTED, peer=uid_a)
        client_a.state = ClientState.CONNECTED
        client_b.state = ClientState.CONNECTED

        return mock_server, client_a, client_b, uid_a, uid_b

    def test_disconnect_resets_client_state(self, connected_setup):
        """After disconnect, client_a should be back to LIVE."""
        _, client_a, _, _, _ = connected_setup

        with patch('client.client.SocketClient') as MockSocket, \
             patch.object(client_a, 'contact_server'):
            MockSocket.is_connected.return_value = True
            MockSocket.av = MagicMock()
            client_a.disconnect_from_peer()

        assert client_a.state == ClientState.LIVE

    def test_server_resets_both_users_on_disconnect(self, connected_setup):
        """When server.disconnect_peer is called, both users go IDLE."""
        server, _, _, uid_a, uid_b = connected_setup
        from utils.user import UserState

        server.contact_client = MagicMock()
        server.disconnect_peer(uid_a)

        assert server.get_user(uid_a).state == UserState.IDLE
        assert server.get_user(uid_b).state == UserState.IDLE

    def test_server_notifies_peer_on_disconnect(self, connected_setup):
        """Server sends POST /peer_disconnected to the peer's client API."""
        server, _, _, uid_a, uid_b = connected_setup

        server.contact_client = MagicMock()
        server.disconnect_peer(uid_a)

        server.contact_client.assert_called_once_with(
            uid_b, '/peer_disconnected', json={'peer_id': uid_a})

    def test_handle_peer_disconnected_resets_peer_state(self, connected_setup):
        """When peer receives disconnect notification, it goes to LIVE."""
        _, _, client_b, _, _ = connected_setup

        with patch('client.client.SocketClient') as MockSocket:
            MockSocket.is_connected.return_value = True
            MockSocket.av = MagicMock()
            client_b.handle_peer_disconnected('peer_a')

        assert client_b.state == ClientState.LIVE
