"""PeerConnectionManager -- Orchestrates peer-to-peer session lifecycle.

Single responsibility: connecting and disconnecting peers.
Depends on the server for user lookups, state changes, and client notification.
"""
from custom_logging import logger
from exceptions import InvalidStateError
from utils import BadGateway, BadRequest
from utils.user_manager import UserNotFoundError, UserState

HTTP_OK = 200


class PeerConnectionManager:
    """Manages peer connection and disconnection workflows."""

    def __init__(self, server):
        """Initialize with a reference to the server."""
        self._server = server
        logger.debug("PeerConnectionManager initialized")

    def connect(self, user_id, peer_id, session_settings=None):
        """Orchestrate a peer connection between two users.

        Returns (api_endpoint, session_id) for the session.
        """
        logger.info("PeerConnect: user=%s -> peer=%s  settings=%s", user_id, peer_id, session_settings)
        if user_id == peer_id:
            msg = f"Cannot intermediate connection between User {user_id} and self."
            raise BadRequest(msg)

        try:
            user = self._server.get_user(user_id)
        except UserNotFoundError as err:
            msg = f"User {user_id} does not exist."
            raise BadRequest(msg) from err
        try:
            peer = self._server.get_user(peer_id)
        except UserNotFoundError as err:
            msg = f"User {peer_id} does not exist."
            raise BadRequest(msg) from err

        if peer.state != UserState.IDLE:
            msg = f"Cannot connect to peer User {peer_id}: peer must be IDLE."
            raise InvalidStateError(msg)
        if user.state != UserState.IDLE:
            msg = f"Cannot connect User {user_id} to peer: User must be IDLE."
            raise InvalidStateError(msg)

        logger.info("Contacting User %s to connect to User %s.", peer_id, user_id)

        session_id = self._server.start_websocket(users=(user_id, peer_id))

        peer_json = {
            "peer_id": user_id,
            "socket_endpoint": tuple(self._server.api_endpoint),
            "session_id": session_id,
        }
        if session_settings is not None:
            peer_json["session_settings"] = session_settings

        try:
            response = self._server.contact_client(peer_id, "/peer_connection", json=peer_json)
        except (ConnectionError, OSError) as err:
            msg = f"Unable to reach peer User {peer_id}."
            raise BadGateway(msg) from err

        if response.status_code != HTTP_OK:
            logger.error("Peer User %s refused connection request.", peer_id)
            msg = f"Peer User {peer_id} refused connection request."
            raise BadGateway(msg)
        logger.info("Peer User %s accepted connection request.", peer_id)

        # Both users are now connected to each other.
        self._server.set_user_state(user_id, UserState.CONNECTED, peer=peer_id)
        self._server.set_user_state(peer_id, UserState.CONNECTED, peer=user_id)
        self._server._log_event("peer_connected", user_id=user_id, peer_id=peer_id)  # noqa: SLF001

        return self._server.api_endpoint, session_id

    def disconnect(self, user_id):
        """Disconnect a user from their active peer session.

        Resets both the user and their peer to IDLE state and sends a
        best-effort notification to the peer's client API.
        """
        logger.info("PeerDisconnect: user=%s", user_id)
        try:
            user = self._server.get_user(user_id)
        except UserNotFoundError as err:
            msg = f"User {user_id} does not exist."
            raise BadRequest(msg) from err

        peer_id = user.peer
        if peer_id is None:
            logger.info("User %s has no active peer -- nothing to disconnect.", user_id)
            return

        # Reset both users to IDLE
        try:
            self._server.set_user_state(user_id, UserState.IDLE)
        except (UserNotFoundError, InvalidStateError) as e:
            logger.error("Failed to reset User %s state: %s", user_id, e)

        try:
            self._server.set_user_state(peer_id, UserState.IDLE)
        except (UserNotFoundError, InvalidStateError) as e:
            logger.error("Failed to reset peer User %s state: %s", peer_id, e)

        self._server._log_event("peer_disconnected", user_id=user_id, peer_id=peer_id)  # noqa: SLF001

        # Best-effort notification to the peer
        try:
            self._server.contact_client(peer_id, "/peer_disconnected", json={
                "peer_id": user_id,
            })
        except (ConnectionError, OSError) as e:
            logger.warning("Could not notify peer User %s of disconnect: %s", peer_id, e)
