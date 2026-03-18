from client.api import ClientAPI
from client.socket_client import SocketClient
from client.server_comms import ServerCommsMixin
from client.endpoint import Endpoint
from client.errors import Errors
from client.util import get_parameters, ClientState
from shared.adapters import FrontendAdapter
from custom_logging import logger


# region --- Main Client ---


class Client(ServerCommsMixin):
    def __init__(self, adapter: FrontendAdapter, server_endpoint=None,
                 api_endpoint=None, websocket_endpoint=None):
        logger.info(f"""Initializing Client with:
                         Server endpoint {server_endpoint},
                         Client API endpoint {api_endpoint},
                         WebSocket API endpoint {websocket_endpoint}.""")
        self.user_id = None
        self.state = ClientState.NEW
        self.adapter = adapter
        self.server_endpoint = server_endpoint
        self.api_endpoint = api_endpoint
        self.websocket_endpoint = websocket_endpoint
        self.peer_endpoint = None
        self.api_instance = None
        self.websocket_instance = None

        self.gui = None
        self.start_api()
        self.connect()

    # region --- Utils ---

    def set_server_endpoint(self, endpoint):
        if self.state >= ClientState.LIVE:
            raise Errors.INTERNALCLIENTERROR.value(
                "Cannot change server endpoint after connection already established.")
        self.server_endpoint = Endpoint(*endpoint)
        logger.info(f"Setting server endpoint: {self.server_endpoint}")

    def set_api_endpoint(self, endpoint):
        if self.state >= ClientState.LIVE:
            raise Errors.INTERNALCLIENTERROR.value(
                "Cannot change API endpoint after connection already established.")
        self.api_endpoint = Endpoint(*endpoint)
        if self.api_instance:
            self.api_instance.endpoint = self.api_endpoint
        logger.info(f"Setting API endpoint: {self.api_endpoint}")

    def display_message(self, user_id, msg):
        print(f"({user_id}): {msg}")

    def kill(self):
        try:
            if self.api_instance:
                self.api_instance.kill()
        except Exception:
            pass
        try:
            if self.websocket_instance:
                self.websocket_instance.kill()
        except Exception:
            pass
        self.disconnect_from_server()

    # endregion

    # region --- Client API Handlers ---

    def start_api(self):
        if not self.api_endpoint:
            raise Errors.INTERNALCLIENTERROR.value(
                "Cannot start Client API without defined endpoint.")
        self.api_instance = ClientAPI(self)
        self.api_instance.start()

    def handle_peer_connection(self, peer_id, socket_endpoint, session_settings=None):
        """
        Initialize Socket Client and attempt connection to specified Socket API endpoint.
        When session_settings is provided (from the host), those shared settings override
        local config for AV initialization. Return `True` iff connection is successful.
        """
        if self.state == ClientState.CONNECTED:
            raise Errors.INTERNALCLIENTERROR.value(
                f"Cannot attempt peer websocket connection while {self.state}.")

        logger.info("Polling User")
        print(f"Incoming connection request from {peer_id}.")
        logger.info("User Accepted Connection.")
        logger.info(f"Attempting to connect to peer {peer_id} at {socket_endpoint}.")
        self.adapter.send_status('peer_incoming', {'peer_id': peer_id})

        try:
            self.connect_to_websocket(socket_endpoint, session_settings=session_settings)
            self.state = ClientState.CONNECTED
            self.adapter.send_status('peer_connected')
            return True
        except Exception as e:
            logger.error(f"Connection to incoming peer User {peer_id} failed: {e}")
            return False

    def disconnect_from_peer(self):
        """Disconnect from the current peer call and return to LIVE state."""
        if self.state != ClientState.CONNECTED:
            logger.info(f"disconnect_from_peer called but state is {self.state} — ignoring.")
            return

        ws = self.websocket_instance

        # Stop AV key rotation
        try:
            if ws and ws.av and hasattr(ws.av, '_key_stop'):
                ws.av._key_stop.set()
        except Exception as e:
            logger.warning(f"Failed to stop key rotation: {e}")

        # Disconnect from websocket
        try:
            if ws and ws.is_connected():
                ws.disconnect()
        except Exception as e:
            logger.warning(f"Failed to disconnect SocketClient: {e}")

        # Notify server
        try:
            self.contact_server('/disconnect_peer', json={
                'user_id': self.user_id
            })
        except Exception as e:
            logger.warning(f"Failed to notify server of disconnect: {e}")

        self.websocket_instance = None
        self.adapter.send_status('peer_disconnected')
        self.state = ClientState.LIVE

    def handle_peer_disconnected(self, peer_id):
        """Called when server notifies us that our peer disconnected."""
        if self.state != ClientState.CONNECTED:
            logger.info(f"handle_peer_disconnected called but state is {self.state} — ignoring.")
            return
        logger.info(f"Peer {peer_id} disconnected from call.")

        ws = self.websocket_instance

        # Stop AV key rotation
        try:
            if ws and ws.av and hasattr(ws.av, '_key_stop'):
                ws.av._key_stop.set()
        except Exception as e:
            logger.warning(f"Failed to stop key rotation: {e}")

        # Disconnect from websocket
        try:
            if ws and ws.is_connected():
                ws.disconnect()
        except Exception as e:
            logger.warning(f"Failed to disconnect SocketClient: {e}")

        self.websocket_instance = None
        self.adapter.send_status('peer_disconnected', {'peer_id': peer_id})
        self.state = ClientState.LIVE

    # endregion

    # region --- Web Socket Interface ---

    def connect_to_websocket(self, endpoint, session_settings=None):
        self.websocket_instance = SocketClient(
            endpoint, self.user_id,
            self.display_message, self.adapter,
            session_settings=session_settings)
        try:
            self.websocket_instance.start()
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket at {endpoint}.")
            raise e

    # endregion

# endregion
