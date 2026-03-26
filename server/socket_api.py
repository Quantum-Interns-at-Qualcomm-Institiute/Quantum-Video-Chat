import logging
import string
import random
import uuid

from flask import request as flask_request
from flask_socketio import SocketIO, send, join_room, leave_room

from state import SocketState
from utils import ServerError
from utils.av import generate_flask_namespace


class SocketAPI:
    """WebSocket API for peer-to-peer session communication.

    Accepts a shared SocketIO instance (created by ServerAPI) and registers
    event handlers on it.  Uses Socket.IO rooms to isolate sessions.
    """

    def __init__(self, server, socketio: SocketIO):
        self.logger = logging.getLogger('SocketAPI')
        self.socketio = socketio
        self.server = server

        # Session management: room-based isolation
        self.sessions: dict[str, set[str]] = {}   # session_id -> {user_id, ...}
        self.sids: dict[str, tuple[str, str]] = {} # sid -> (session_id, user_id)

        # Register event handlers
        self._register_events()

        # Register AV namespaces
        self.namespaces = generate_flask_namespace(self)
        ns = sorted(list(self.namespaces.keys()))
        for name in ns:
            self.socketio.on_namespace(self.namespaces[name])

        self.logger.info("SocketAPI initialized with shared SocketIO instance.")

    # Event name -> method name mapping.
    EVENT_HANDLERS = {
        'connect':     '_on_connect',
        'message':     '_on_message',
        'frame':       '_on_frame',
        'audio-frame': '_on_audio_frame',
        'disconnect':  '_on_disconnect',
    }

    def _register_events(self):
        """Wire up socket.io events from the EVENT_HANDLERS registry."""
        for event, method_name in self.EVENT_HANDLERS.items():
            handler = getattr(self, method_name)
            self.socketio.on(event)(handler)

    def create_session(self, users) -> str:
        """Create a new session room for the given users. Returns session_id."""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = set(users)
        self.logger.info(f"Created session {session_id} for users {users}")
        return session_id

    # region --- Event Handlers ---

    def _on_connect(self, auth=None):
        if not isinstance(auth, dict):
            self.logger.info("Socket connection rejected: no auth dict provided.")
            return False

        user_id = auth.get('user_id')
        session_id = auth.get('session_id')

        self.logger.info(f"Received Socket connection request from User {user_id} for session {session_id}.")

        if not session_id or session_id not in self.sessions:
            self.logger.info(f"Socket connection rejected: unknown session {session_id}.")
            return False

        expected_users = self.sessions[session_id]
        if user_id not in expected_users:
            self.logger.info(f"Socket connection rejected: User {user_id} not expected in session {session_id}.")
            return False

        sid = flask_request.sid
        self.logger.info(f"Socket connection from User {user_id} accepted (session={session_id})")

        join_room(session_id)
        self.sids[sid] = (session_id, user_id)

        # Check if all expected users are now connected
        connected_users = {uid for (sess_id, uid) in self.sids.values() if sess_id == session_id}
        if connected_users >= expected_users:
            self.logger.info(f"Session {session_id} acquired all expected users.")
            room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            self.logger.info(f"All users connected — emitting room-id '{room_id}' to session {session_id}")
            self.socketio.emit('room-id', room_id, to=session_id)

    def _on_message(self, user_id, msg):
        self.logger.info(f"Received message from User {user_id}: '{msg}'")
        sid = flask_request.sid
        session_info = self.sids.get(sid)
        if session_info:
            session_id, _ = session_info
            send((user_id, msg), to=session_id)

    def _on_frame(self, data):
        """Relay a video frame to all other users in the same session room."""
        sender_sid = flask_request.sid
        session_info = self.sids.get(sender_sid)
        if not session_info:
            return
        session_id, sender_id = session_info
        self.socketio.emit('frame', {
            'frame':  data.get('frame'),
            'width':  data.get('width'),
            'height': data.get('height'),
            'sender': sender_id,
        }, to=session_id, skip_sid=sender_sid)

    def _on_audio_frame(self, data):
        """Relay an audio chunk to all other users in the same session room."""
        sender_sid = flask_request.sid
        session_info = self.sids.get(sender_sid)
        if not session_info:
            return
        session_id, sender_id = session_info
        self.socketio.emit('audio-frame', {
            'audio':       data.get('audio'),
            'sample_rate': data.get('sample_rate'),
            'sender':      sender_id,
        }, to=session_id, skip_sid=sender_sid)

    def _on_disconnect(self):
        sid = flask_request.sid
        session_info = self.sids.pop(sid, None)
        if session_info:
            session_id, user_id = session_info
            self.logger.info(f"Client disconnected (sid={sid}, user_id={user_id}, session={session_id}).")
            leave_room(session_id)
        else:
            self.logger.info(f"Client disconnected (sid={sid}, unknown session).")

        # NOTE: We intentionally do NOT call server.disconnect_peer() here.
        # Transient socket disconnections (network blip, reconnection) should
        # not tear down the entire peer session.  The explicit REST endpoint
        # POST /disconnect_peer (called by leave_room) is the authoritative
        # signal that a user wants to leave.

    # endregion

    # region --- QBER Event Broadcasting ---

    def emit_qber_update(self, event_type: str, data: dict, session_id: str = None):
        """Broadcast QBER metrics to connected clients.

        Called by the AV layer's key rotation thread when a BB84 round
        completes or is aborted due to intrusion detection.
        """
        kwargs = {}
        if session_id:
            kwargs['to'] = session_id
        self.socketio.emit('qber-update', {
            'event': event_type,
            **data,
        }, **kwargs)

    # endregion
