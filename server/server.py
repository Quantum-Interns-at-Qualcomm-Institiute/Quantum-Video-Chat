"""QKD server -- manages users, peer connections, and WebSocket sessions."""

import time
from collections import deque
from datetime import UTC, datetime

from client_notifier import ClientNotifier
from custom_logging import logger
from exceptions import InvalidStateError
from peer_manager import PeerConnectionManager
from socket_api import SocketAPI
from utils import Endpoint, ServerError
from utils.user_manager import DuplicateUserError, UserManager, UserNotFoundError, UserState, UserStorageFactory


# region --- Server ---
class Server:
    """Core QKD server managing users, sessions, and peer connections."""

    # TODO: make user storage type pull from config file
    def __init__(self, api_endpoint, user_storage="DICT", socketio=None):
        """Initialize the server with endpoint, user storage, and optional WebSocket."""
        self.api_endpoint = Endpoint(*api_endpoint)
        logger.info("Initializing server with API Endpoint %s", self.api_endpoint)

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
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "event": event,
            **details,
        })

    def add_user(self, api_endpoint):
        """Add a new user and return their generated user ID."""
        try:
            user_id = self.user_manager.add_user(api_endpoint)
            logger.info("User %s added.", user_id)
            self._log_event("user_added", user_id=user_id)
        except DuplicateUserError as e:
            logger.error(str(e))
            raise
        else:
            return user_id

    def get_user(self, user_id):
        """Retrieve a user by ID."""
        try:
            user_info = self.user_manager.get_user(user_id)
            logger.info("Retrieved user with ID %s.", user_id)
        except UserNotFoundError as e:
            logger.error(str(e))
            raise
        else:
            return user_info

    def remove_user(self, user_id):
        """Remove a user from the server."""
        try:
            self.user_manager.remove_user(user_id)
            logger.info("User %s removed successfully.", user_id)
            self._log_event("user_removed", user_id=user_id)
        except UserNotFoundError as e:
            logger.error(str(e))
            raise

    def set_user_state(self, user_id, state: UserState, peer=None):
        """Update a user's connection state and optional peer."""
        try:
            self.user_manager.set_user_state(user_id, state, peer)
            logger.info("Updated User %s state: %s (%s).", user_id, state, peer)
        except (UserNotFoundError, InvalidStateError) as e:
            logger.error(str(e))
            raise

    def contact_client(self, user_id, route, json):
        """Delegate to ClientNotifier."""
        return self.notifier.notify(user_id, route, json)

    def start_websocket(self, users):
        """Create a new session room for the given users. Returns session_id."""
        logger.info("Creating WebSocket session.")
        if self.socket_api is None:
            msg = "Cannot start WebSocket session without SocketAPI."
            raise ServerError(msg)
        return self.socket_api.create_session(users)

    def disconnect_peer(self, user_id):
        """Delegate to PeerConnectionManager."""
        self.peer_manager.disconnect(user_id)

    def handle_peer_connection(self, user_id, peer_id, session_settings=None):
        """Delegate to PeerConnectionManager."""
        return self.peer_manager.connect(user_id, peer_id, session_settings)

# endregion
