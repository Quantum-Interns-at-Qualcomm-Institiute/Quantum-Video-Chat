"""
PeerConnectionManager — Orchestrates peer-to-peer session lifecycle.

Single responsibility: connecting and disconnecting peers.
Depends on the server for user lookups, state changes, and client notification.
"""
from custom_logging import logger
from utils import BadGateway, BadRequest
from utils.user_manager import UserState, UserNotFound
from exceptions import InvalidState


class PeerConnectionManager:
    """Manages peer connection and disconnection workflows."""

    def __init__(self, server):
        self._server = server

    def connect(self, user_id, peer_id, session_settings=None):
        """Orchestrate a peer connection between two users.

        Returns the websocket endpoint for the session.
        """
        if user_id == peer_id:
            raise BadRequest(f"Cannot intermediate connection between User {user_id} and self.")

        try:
            user = self._server.get_user(user_id)
        except UserNotFound:
            raise BadRequest(f"User {user_id} does not exist.")
        try:
            peer = self._server.get_user(peer_id)
        except UserNotFound:
            raise BadRequest(f"User {peer_id} does not exist.")

        if peer.state != UserState.IDLE:
            raise InvalidState(f"Cannot connect to peer User {peer_id}: peer must be IDLE.")
        if user.state != UserState.IDLE:
            raise InvalidState(f"Cannot connect User {user_id} to peer: User must be IDLE.")

        logger.info(f"Contacting User {peer_id} to connect to User {user_id}.")

        self._server.start_websocket(users=(user_id, peer_id))

        peer_json = {
            'peer_id': user_id,
            'socket_endpoint': tuple(self._server.websocket_endpoint),
        }
        if session_settings is not None:
            peer_json['session_settings'] = session_settings

        try:
            response = self._server.contact_client(peer_id, '/peer_connection', json=peer_json)
        except Exception:
            raise BadGateway(f"Unable to reach peer User {peer_id}.")

        if response.status_code != 200:
            logger.error(f"Peer User {peer_id} refused connection request.")
            raise BadGateway(f"Peer User {peer_id} refused connection request.")
        logger.info(f"Peer User {peer_id} accepted connection request.")

        # Both users are now connected to each other.
        self._server.set_user_state(user_id, UserState.CONNECTED, peer=peer_id)
        self._server.set_user_state(peer_id, UserState.CONNECTED, peer=user_id)
        self._server._log_event('peer_connected', user_id=user_id, peer_id=peer_id)

        return self._server.websocket_endpoint

    def disconnect(self, user_id):
        """Disconnect a user from their active peer session.

        Resets both the user and their peer to IDLE state and sends a
        best-effort notification to the peer's client API.
        """
        try:
            user = self._server.get_user(user_id)
        except UserNotFound:
            raise BadRequest(f"User {user_id} does not exist.")

        peer_id = user.peer
        if peer_id is None:
            logger.info(f"User {user_id} has no active peer — nothing to disconnect.")
            return

        # Reset both users to IDLE
        try:
            self._server.set_user_state(user_id, UserState.IDLE)
        except Exception as e:
            logger.error(f"Failed to reset User {user_id} state: {e}")

        try:
            self._server.set_user_state(peer_id, UserState.IDLE)
        except Exception as e:
            logger.error(f"Failed to reset peer User {peer_id} state: {e}")

        self._server._log_event('peer_disconnected', user_id=user_id, peer_id=peer_id)

        # Best-effort notification to the peer
        try:
            self._server.contact_client(peer_id, '/peer_disconnected', json={
                'peer_id': user_id,
            })
        except Exception as e:
            logger.warning(f"Could not notify peer User {peer_id} of disconnect: {e}")
