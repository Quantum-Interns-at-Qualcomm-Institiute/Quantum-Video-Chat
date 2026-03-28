"""events -- Register all socket.io event handlers.

Single responsibility: wiring socket events to handler functions.
Keeps client.py as a thin entry point.
"""
import gevent
import server_comms
from flask import jsonify
from flask import request as flask_request
from state import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, HEIGHT, IS_LOCAL, WIDTH, MiddlewareState  # noqa: F401

from shared.logging import get_logger

logger = get_logger(__name__)


def register_browser_events(state: MiddlewareState):  # noqa: C901 -- event registration is inherently multi-branched
    """Register browser <-> middleware socket.io event handlers."""
    import time
    import uuid
    sio = state.sio

    # Browser client tracking: {client_id: {"sid": sid, "last_seen": monotonic}}
    state._browser_clients = {}
    # Reverse map: sid -> client_id for cleanup on disconnect
    state._sid_to_client = {}

    _HEARTBEAT_INTERVAL = 25  # seconds

    def _start_ping_loop():
        """Background greenlet: emit ping to all connected browsers every HEARTBEAT_INTERVAL seconds."""
        logger.debug("Heartbeat ping loop started (interval=%ss)", _HEARTBEAT_INTERVAL)
        while True:
            gevent.sleep(_HEARTBEAT_INTERVAL)
            n_clients = len(state._browser_clients)
            if n_clients:
                logger.debug("Sending server-ping to %d browser client(s)", n_clients)
            ts = time.time()
            for client_id, info in list(state._browser_clients.items()):
                try:
                    sio.emit("server-ping", {"ts": ts, "client_id": client_id}, room=info["sid"])
                except Exception:
                    logger.debug("Failed to send ping to client_id=%s", client_id)
            # Sweep stale clients (no pong in 90s)
            now = time.monotonic()
            for client_id, info in list(state._browser_clients.items()):
                if now - info["last_seen"] > 90:
                    logger.info("Sweeping stale browser client %s (sid=%s)", client_id, info["sid"])
                    state._sid_to_client.pop(info["sid"], None)
                    del state._browser_clients[client_id]

    gevent.spawn(_start_ping_loop)
    logger.debug("Browser event handlers registering")

    @sio.event
    def connect(sid, _environ):
        client_id = str(uuid.uuid4())
        state._browser_clients[client_id] = {"sid": sid, "last_seen": time.monotonic()}
        state._sid_to_client[sid] = client_id
        logger.info("Browser connected  sid=%s  client_id=%s  total=%d",
                     sid, client_id, len(state._browser_clients))
        sio.emit("welcome", {
            "client_id":          client_id,
            "heartbeat_interval": _HEARTBEAT_INTERVAL,
            "host":               DEFAULT_SERVER_HOST,
            "port":               DEFAULT_SERVER_PORT,
            "isLocal":            IS_LOCAL,
        }, room=sid)
        logger.debug("Sent welcome to sid=%s  host=%s:%s  isLocal=%s",
                      sid, DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, IS_LOCAL)
        if state.server_alive:
            sio.emit("server-connected", room=sid)
            logger.debug("Sent server-connected to sid=%s (server already alive)", sid)

    @sio.event
    def pong(sid, data=None):
        """Browser responds to our server-ping."""
        data = data or {}
        client_id = data.get("client_id") or state._sid_to_client.get(sid)
        if client_id and client_id in state._browser_clients:
            state._browser_clients[client_id]["last_seen"] = time.monotonic()
            logger.debug("Heartbeat pong from client_id=%s", client_id)

    @sio.event
    def disconnect(sid):
        client_id = state._sid_to_client.pop(sid, None)
        if client_id:
            state._browser_clients.pop(client_id, None)
        logger.info("Browser disconnected sid=%s  client_id=%s  remaining=%d",
                     sid, client_id, len(state._browser_clients))

    @sio.event
    def toggle_camera(_sid, data):
        enabled = bool(data.get("enabled", True))
        state.camera_enabled = enabled
        logger.info("Camera %s", "enabled" if enabled else "disabled")

    @sio.event
    def toggle_mute(_sid, data):
        muted = bool(data.get("muted", False))
        state.muted = muted
        logger.info("Microphone %s", "muted" if muted else "unmuted")

    @sio.event
    def select_camera(_sid, data):
        device = int(data.get("device", 0))
        state.camera_device = device
        logger.info("Camera device changed to %s", device)
        server_comms.start_video(state, None)

    @sio.event
    def list_cameras(sid):
        """Enumerate available video capture devices and send back to browser."""
        logger.debug("list_cameras requested by sid=%s", sid)
        devices = server_comms.enumerate_cameras()
        logger.debug("Returning %d camera(s) to sid=%s", len(devices), sid)
        sio.emit("camera-list", devices, room=sid)

    @sio.event
    def select_audio(_sid, data):
        device = int(data.get("device", 0))
        state.audio_device = device
        logger.info("Audio device changed to %s", device)
        if state.audio_thread is not None and state.audio_thread.is_alive():
            logger.debug("Restarting audio thread for new device")
            state.audio_thread.stop()
            state.audio_thread.join(timeout=2)
            server_comms.start_audio(state, None)

    @sio.event
    def list_audio_devices(sid):
        """Enumerate available audio input devices and send back to browser."""
        logger.debug("list_audio_devices requested by sid=%s", sid)
        devices = server_comms.enumerate_audio_devices()
        logger.debug("Returning %d audio device(s) to sid=%s", len(devices), sid)
        sio.emit("audio-device-list", devices, room=sid)

    @sio.event
    def configure_server(sid, data):
        logger.info("configure_server from sid=%s  data=%s", sid, data)
        g = gevent.spawn(server_comms.configure_server, state, sid, data)
        g.join(timeout=10)
        if not g.dead:
            logger.warning("configure_server greenlet timed out after 10s")

    @sio.event
    def create_user(sid):
        logger.info("create_user from sid=%s", sid)
        server_comms.create_user(state, sid)

    @sio.event
    def join_room(sid, peer_id=None):
        logger.info("join_room from sid=%s  peer_id=%s", sid, peer_id)
        server_comms.join_room(state, sid, peer_id)

    @sio.event
    def leave_room(sid):
        logger.info("leave_room from sid=%s", sid)
        server_comms.leave_room(state, sid)

    logger.debug("All browser event handlers registered")


def register_server_events(state: MiddlewareState):
    """Register QKD server -> middleware socket.io event handlers."""
    sc = state.server_client
    logger.debug("Registering QKD server event handlers")

    @sc.on("connect")
    def _server_connect():
        logger.info("Connected to QKD server via session WebSocket")

    @sc.on("disconnect")
    def _server_disconnect():
        logger.info("Disconnected from QKD server session WebSocket")
        # NOTE: We do NOT stop media threads here.  The socketio.Client may
        # reconnect automatically after a transient network blip.  Media
        # threads are stopped explicitly by leave_room or /peer_disconnected.

    @sc.on("room-id")
    def _server_room_id(room_id):
        logger.info("room-id '%s' -- starting media threads", room_id)
        state.sio.emit("room-id", room_id)
        server_comms.start_video(state, room_id)
        server_comms.start_audio(state, room_id)

    @sc.on("frame")
    def _server_frame(data):
        if data.get("sender") is None:
            return  # echo of own frame; ignore
        frame = data.get("frame")
        if frame is not None:
            state.sio.emit("frame", {
                "frame":  frame,
                "width":  data.get("width", WIDTH),
                "height": data.get("height", HEIGHT),
                "self":   False,
            })

    @sc.on("audio-frame")
    def _server_audio_frame(data):
        if data.get("sender") is None:
            return  # echo of own audio; ignore
        audio = data.get("audio")
        if audio is not None:
            state.sio.emit("audio-frame", {
                "audio":       audio,
                "sample_rate": data.get("sample_rate", 8000),
                "self":        False,
            })

    logger.debug("All QKD server event handlers registered")


def register_rest_routes(state: MiddlewareState):
    """Register Flask REST routes that the QKD server calls."""
    import time
    flask_app = state.flask_app
    state._start_time = time.monotonic()
    logger.debug("Registering middleware REST routes")

    @flask_app.route("/health", methods=["GET"])
    def _rest_health():
        uptime = time.monotonic() - state._start_time
        n_clients = len(getattr(state, "_browser_clients", {}))
        logger.debug("GET /health  uptime=%.1f  clients=%d", uptime, n_clients)
        return jsonify({
            "status": "ok",
            "uptime": round(uptime, 1),
            "clients": n_clients,
        }), 200

    @flask_app.route("/disconnect", methods=["POST"])
    def _rest_disconnect():
        # Accept both JSON and sendBeacon blob (application/json content)
        data = flask_request.get_json(force=True, silent=True) or {}
        client_id = data.get("client_id", "")
        logger.debug("POST /disconnect  client_id=%s", client_id)
        if client_id:
            clients = getattr(state, "_browser_clients", {})
            if client_id in clients:
                del clients[client_id]
                logger.info("Browser client %s gracefully disconnected (beacon)", client_id)
            else:
                logger.debug("POST /disconnect  client_id=%s not found (already gone)", client_id)
        return "", 204

    @flask_app.route("/peer_connection", methods=["POST"])
    def _rest_peer_connection():
        data = flask_request.get_json(force=True)
        peer_id = data.get("peer_id", "")
        ws_endpoint = data.get("socket_endpoint")
        session_id = data.get("session_id")
        logger.info("POST /peer_connection  peer=%s  ws=%s  session=%s", peer_id, ws_endpoint, session_id)
        if ws_endpoint:
            gevent.spawn(server_comms.connect_to_session_ws, state, ws_endpoint, peer_id, session_id=session_id)
        return jsonify({"status": "ok"}), 200

    @flask_app.route("/peer_disconnected", methods=["POST"])
    def _rest_peer_disconnected():
        data = flask_request.get_json(force=True)
        peer_id = data.get("peer_id", "")
        logger.info("POST /peer_disconnected  peer=%s", peer_id)
        state.sio.emit("peer-disconnected", {"peer_id": peer_id})
        if state.video_thread is not None:
            logger.debug("Stopping video thread (peer disconnected)")
            state.video_thread.stop()
            state.video_thread = None
        if state.audio_thread is not None:
            logger.debug("Stopping audio thread (peer disconnected)")
            state.audio_thread.stop()
            state.audio_thread = None
        if state.server_client.connected:
            try:
                logger.debug("Disconnecting server_client WebSocket")
                state.server_client.disconnect()
            except (ConnectionError, OSError):
                logger.debug("Ignoring error during server_client disconnect")
        return jsonify({"status": "ok"}), 200

    logger.debug("All middleware REST routes registered")
