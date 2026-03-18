import time
from collections import deque
from datetime import datetime

from exceptions import InvalidState

from custom_logging import logger
from utils import ServerError, Endpoint
from utils.user_manager import UserManager, UserStorageFactory, UserState
from utils.user_manager import DuplicateUser, UserNotFound
from shared.config import LOCAL_IP, SERVER_WEBSOCKET_PORT
from peer_manager import PeerConnectionManager
from client_notifier import ClientNotifier


# region --- Server ---
class Server:
    # TODO: make user storage type pull from config file
    def __init__(self, api_endpoint, user_storage="DICT"):
        from socket_api import SocketAPI  # late import to avoid circular dependency
        self._SocketAPI = SocketAPI

        self.api_endpoint = Endpoint(*api_endpoint)
        logger.info(f"Intializing server with API Endpoint {self.api_endpoint}")

        self.websocket_endpoint = Endpoint(LOCAL_IP, SERVER_WEBSOCKET_PORT)
        self.start_time = time.time()
        self.event_log = deque(maxlen=500)

        with UserStorageFactory() as factory:
            storage = factory.create_storage(user_storage)
            self.user_manager = UserManager(storage=storage)
        self.qber_manager = None  # QBERManager

        self.notifier = ClientNotifier(self)
        self.peer_manager = PeerConnectionManager(self)

    def _log_event(self, event, **details):
        self.event_log.append({
            'timestamp': datetime.now().isoformat(),
            'event': event,
            **details,
        })

    def add_user(self, api_endpoint):
        try:
            user_id = self.user_manager.add_user(api_endpoint)
            logger.info(f"User {user_id} added.")
            self._log_event('user_added', user_id=user_id)
            return user_id
        except DuplicateUser as e:
            logger.error(str(e))
            raise e

    def get_user(self, user_id):
        try:
            user_info = self.user_manager.get_user(user_id)
            logger.info(f"Retrieved user with ID {user_id}.")
            return user_info
        except UserNotFound as e:
            logger.error(str(e))
            raise e

    def remove_user(self, user_id):
        try:
            self.user_manager.remove_user(user_id)
            logger.info(f"User {user_id} removed successfully.")
            self._log_event('user_removed', user_id=user_id)
        except UserNotFound as e:
            logger.error(str(e))
            raise e

    def set_user_state(self, user_id, state: UserState, peer=None):
        try:
            self.user_manager.set_user_state(user_id, state, peer)
            logger.info(f"Updated User {user_id} state: {state} ({peer}).")
        except (UserNotFound, InvalidState) as e:
            logger.error(str(e))
            raise e

    def contact_client(self, user_id, route, json):
        """Delegate to ClientNotifier."""
        return self.notifier.notify(user_id, route, json)

    def set_websocket_endpoint(self, endpoint):
        self.websocket_endpoint = Endpoint(*endpoint)
        if hasattr(self, 'websocket_instance') and self.websocket_instance:
            self.websocket_instance.endpoint = self.websocket_endpoint
        logger.info(f"Setting Web Socket endpoint: {self.websocket_endpoint}")

    def start_websocket(self, users):
        logger.info("Starting WebSocket API.")
        if not self.websocket_endpoint:
            raise ServerError("Cannot start WebSocket API without defined endpoint.")

        # Kill any previous SocketAPI instance so we don't leak threads and ports.
        if hasattr(self, 'websocket_instance') and self.websocket_instance is not None:
            try:
                self.websocket_instance.kill()
                logger.info("Killed previous WebSocket API instance.")
            except Exception as e:
                logger.warning(f"Could not kill previous WebSocket API: {e}")
            # Reset the endpoint back to the default so the new instance doesn't
            # inherit a bumped port from a previous session.
            self.websocket_endpoint = Endpoint(LOCAL_IP, SERVER_WEBSOCKET_PORT)

        self.websocket_instance = self._SocketAPI(self, users)
        self.websocket_instance.start()
        # Wait until the WebSocket server is actually accepting connections
        # before returning the endpoint to callers.
        if not self.websocket_instance.wait_until_ready(timeout=5.0):
            logger.warning("WebSocket API did not become ready within 5s — "
                           "clients may need to retry.")

    def disconnect_peer(self, user_id):
        """Delegate to PeerConnectionManager."""
        self.peer_manager.disconnect(user_id)

    def handle_peer_connection(self, user_id, peer_id, session_settings=None):
        """Delegate to PeerConnectionManager."""
        return self.peer_manager.connect(user_id, peer_id, session_settings)

# endregion
