import time
from collections import deque
from datetime import datetime

from client_notifier import ClientNotifier
from custom_logging import logger
from exceptions import InvalidState
from peer_manager import PeerConnectionManager
from socket_api import SocketAPI
from utils import Endpoint, ServerError
from utils.user_manager import DuplicateUser, UserManager, UserNotFound, UserState, UserStorageFactory


# region --- Server ---
class Server:
    # TODO: make user storage type pull from config file
    def __init__(self, api_endpoint, user_storage="DICT", socketio=None):
        self.api_endpoint = Endpoint(*api_endpoint)
        logger.info(f"Initializing server with API Endpoint {self.api_endpoint}")

        self.start_time = time.time()
        self.event_log = deque(maxlen=500)

        with UserStorageFactory() as factory:
            storage = factory.create_storage(user_storage)
            self.user_manager = UserManager(storage=storage)
        self.qber_monitor = None  # Set by AV when BB84 mode is active
        self.bb84_key_gen = None  # Reference to BB84KeyGenerator for admin API

        self.notifier = ClientNotifier(self)
        self.peer_manager = PeerConnectionManager(self)

        # Create the single SocketAPI instance if socketio is provided
        self.socket_api = SocketAPI(self, socketio) if socketio is not None else None

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

    def start_websocket(self, users):
        """Create a new session room for the given users. Returns session_id."""
        logger.info("Creating WebSocket session.")
        if self.socket_api is None:
            raise ServerError("Cannot start WebSocket session without SocketAPI.")
        session_id = self.socket_api.create_session(users)
        return session_id

    def disconnect_peer(self, user_id):
        """Delegate to PeerConnectionManager."""
        self.peer_manager.disconnect(user_id)

    def handle_peer_connection(self, user_id, peer_id, session_settings=None):
        """Delegate to PeerConnectionManager."""
        return self.peer_manager.connect(user_id, peer_id, session_settings)

# endregion
