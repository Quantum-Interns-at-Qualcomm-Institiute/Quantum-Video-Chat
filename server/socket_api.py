import logging
import string
import random
from threading import Thread, Event

from flask import Flask, request as flask_request
from flask_socketio import SocketIO, send

from state import SocketState
from utils import ServerError, Endpoint
from utils.av import generate_flask_namespace
from shared.config import LOCAL_IP, SERVER_WEBSOCKET_PORT


class SocketAPI:
    """WebSocket API for peer-to-peer session communication.

    Uses composition (owns a Thread) rather than inheriting from Thread,
    so the class can be extended without coupling to threading internals.
    """
    DEFAULT_ENDPOINT = Endpoint(LOCAL_IP, SERVER_WEBSOCKET_PORT)

    def __init__(self, server, users):
        self._thread = None
        self._ready = Event()  # Signalled when the server is actually listening
        self.logger = logging.getLogger('SocketAPI')
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app)
        self.server = server
        self.endpoint = server.websocket_endpoint
        self.state = SocketState.INIT
        self.namespaces = None
        self.users = {}
        self.sids = {}  # Maps socket session ID → user_id for disconnect lookup

        for user in users:
            self.users[user] = None

        # Register event handlers via declarative registry
        self._register_events()

        self.logger.info(f"Initializing WebSocket API with endpoint {self.endpoint}.")

    # Event name → method name mapping. Subclasses can override to
    # add/remove handlers without touching __init__.
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

    def has_all_users(self):
        for user in self.users:
            if not self.users[user]:
                return False
        return True

    def verify_connection(self, user_id):
        return user_id in self.users

    # ── Thread delegation ─────────────────────────────────────────────────

    def start(self):
        """Launch the WebSocket server on a background daemon thread."""
        self._ready.clear()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def wait_until_ready(self, timeout=5.0):
        """Block until the server is actually listening, or timeout.

        Returns True if the server is ready, False on timeout.
        """
        return self._ready.wait(timeout=timeout)

    def is_alive(self):
        """Return True if the background thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout=None):
        """Block until the background thread terminates."""
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self):
        import socket as _socket

        self.namespaces = generate_flask_namespace(self)
        ns = sorted(list(self.namespaces.keys()))
        for name in ns:
            self.socketio.on_namespace(self.namespaces[name])

        self.logger.info("Starting WebSocket API.")
        if self.state == SocketState.NEW:
            raise ServerError("Cannot start API before initialization.")
        if self.state == SocketState.LIVE or self.state == SocketState.OPEN:
            raise ServerError("Cannot start API: already running.")

        while True:
            try:
                self.logger.info(f"Serving WebSocket API at {self.endpoint}")
                self.state = SocketState.LIVE

                # Signal readiness shortly after socketio.run starts.
                # We probe the port in a helper thread to detect when the
                # server is actually accepting connections.
                def _signal_when_listening():
                    import time
                    for _ in range(50):  # up to 5 seconds
                        time.sleep(0.1)
                        try:
                            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                            sock.settimeout(0.5)
                            sock.connect((self.endpoint.ip, self.endpoint.port))
                            sock.close()
                            self._ready.set()
                            return
                        except (ConnectionRefusedError, OSError):
                            continue
                    # Timeout — signal anyway so callers don't block forever
                    self._ready.set()

                probe = Thread(target=_signal_when_listening, daemon=True)
                probe.start()

                self.socketio.run(self.app, host=self.endpoint.ip, port=self.endpoint.port)
            except OSError:
                self.logger.error(f"Endpoint {self.endpoint} in use.")
                self.state = SocketState.INIT
                self.server.set_websocket_endpoint(
                    Endpoint(self.endpoint.ip, self.endpoint.port + 1))
                self.endpoint = self.server.websocket_endpoint
                continue
            self.logger.info("WebSocket API terminated.")
            break

    def kill(self):
        self.logger.info("Killing WebSocket API.")
        if not (self.state == SocketState.LIVE or self.state == SocketState.OPEN):
            raise ServerError(
                f"Cannot kill Socket API when not {SocketState.LIVE} or {SocketState.OPEN}.")
        self.socketio.stop()
        self.state = SocketState.INIT

    # region --- Event Handlers ---

    def _on_connect(self, auth=None):
        # flask_socketio passes the auth dict, not the user_id directly
        user_id = auth.get('user_id') if isinstance(auth, dict) else auth
        self.logger.info(f"Received Socket connection request from User {user_id}.")
        if self.state not in (SocketState.LIVE, SocketState.OPEN):
            self.logger.info(f"Cannot accept connection in state {self.state}.")
            return False
        if not self.verify_connection(user_id):
            self.logger.info("Socket connection failed authentication.")
            return False
        self.logger.info(f"Socket connection from User {user_id} accepted")
        self.users[user_id] = flask_request.sid
        self.sids[flask_request.sid] = user_id
        if self.has_all_users():
            if self.state != SocketState.OPEN:
                self.logger.info("Socket API acquired all expected users.")
                self.state = SocketState.OPEN
            # Generate a room ID and broadcast to all connected clients
            room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            self.logger.info(f"All users connected — emitting room-id '{room_id}'")
            self.socketio.emit('room-id', room_id)

    def _on_message(self, user_id, msg):
        self.logger.info(f"Received message from User {user_id}: '{msg}'")
        send((user_id, msg), broadcast=True)

    def _on_frame(self, data):
        """Relay a video frame from one middleware to all other connected middlewares."""
        sender_sid = flask_request.sid
        sender_id = self.sids.get(sender_sid)
        # Forward to every connected client except the sender
        for user_id, sid in self.users.items():
            if sid and sid != sender_sid:
                self.socketio.emit('frame', {
                    'frame':  data.get('frame'),
                    'width':  data.get('width'),
                    'height': data.get('height'),
                    'sender': sender_id,
                }, to=sid)

    def _on_audio_frame(self, data):
        """Relay an audio chunk from one middleware to all other connected middlewares."""
        sender_sid = flask_request.sid
        sender_id = self.sids.get(sender_sid)
        for user_id, sid in self.users.items():
            if sid and sid != sender_sid:
                self.socketio.emit('audio-frame', {
                    'audio':       data.get('audio'),
                    'sample_rate': data.get('sample_rate'),
                    'sender':      sender_id,
                }, to=sid)

    def _on_disconnect(self):
        sid = flask_request.sid
        user_id = self.sids.pop(sid, None)
        self.logger.info(f"Client disconnected (sid={sid}, user_id={user_id}).")

        # Clear the user's session ID so they can reconnect later.
        if user_id and user_id in self.users:
            self.users[user_id] = None

        # NOTE: We intentionally do NOT call server.disconnect_peer() here.
        # Transient socket disconnections (network blip, reconnection) should
        # not tear down the entire peer session.  The explicit REST endpoint
        # POST /disconnect_peer (called by leave_room) is the authoritative
        # signal that a user wants to leave.

        # If all users have disconnected, revert to LIVE so reconnections
        # are accepted (rather than INIT which would reject them).
        if not self.sids:
            self.logger.info("All users disconnected — reverting to LIVE state.")
            self.state = SocketState.LIVE

    # endregion
