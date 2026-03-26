"""
events — Register all socket.io event handlers.

Single responsibility: wiring socket events to handler functions.
Keeps client.py as a thin entry point.
"""
import gevent
import server_comms
from flask import jsonify
from flask import request as flask_request
from state import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, HEIGHT, IS_LOCAL, WIDTH, MiddlewareState

from shared.logging import get_logger

logger = get_logger(__name__)


def register_browser_events(state: MiddlewareState):
    """Register browser ↔ middleware socket.io event handlers."""
    sio = state.sio

    @sio.event
    def connect(sid, environ):
        logger.info('Browser connected  sid=%s', sid)
        sio.emit('welcome', {
            'host':    DEFAULT_SERVER_HOST,
            'port':    DEFAULT_SERVER_PORT,
            'isLocal': IS_LOCAL,
        }, room=sid)
        if state.server_alive:
            sio.emit('server-connected', room=sid)

    @sio.event
    def ping(sid):
        sio.emit('pong', {
            'server': state.server_alive,
            'user_id': state.user_id,
        }, room=sid)

    @sio.event
    def disconnect(sid):
        logger.info('Browser disconnected sid=%s', sid)

    @sio.event
    def toggle_camera(sid, data):
        state.camera_enabled = bool(data.get('enabled', True))
        logger.info('Camera %s', 'enabled' if state.camera_enabled else 'disabled')

    @sio.event
    def toggle_mute(sid, data):
        state.muted = bool(data.get('muted', False))
        logger.info('Microphone %s', 'muted' if state.muted else 'unmuted')

    @sio.event
    def select_camera(sid, data):
        device = int(data.get('device', 0))
        state.camera_device = device
        logger.info('Camera device set to %s', device)
        # Start or restart video thread for preview (and in-call use).
        # The thread naturally only sends to the server when connected.
        server_comms.start_video(state, None)

    @sio.event
    def list_cameras(sid):
        """Enumerate available video capture devices and send back to browser."""
        devices = server_comms.enumerate_cameras()
        sio.emit('camera-list', devices, room=sid)

    @sio.event
    def select_audio(sid, data):
        device = int(data.get('device', 0))
        state.audio_device = device
        logger.info('Audio device set to %s', device)
        # If audio thread is running, restart it with the new device
        if state.audio_thread is not None and state.audio_thread.is_alive():
            state.audio_thread.stop()
            state.audio_thread.join(timeout=2)
            server_comms.start_audio(state, None)

    @sio.event
    def list_audio_devices(sid):
        """Enumerate available audio input devices and send back to browser."""
        devices = server_comms.enumerate_audio_devices()
        sio.emit('audio-device-list', devices, room=sid)

    @sio.event
    def configure_server(sid, data):
        server_comms.configure_server(state, sid, data)

    @sio.event
    def create_user(sid):
        server_comms.create_user(state, sid)

    @sio.event
    def join_room(sid, peer_id=None):
        server_comms.join_room(state, sid, peer_id)

    @sio.event
    def leave_room(sid):
        server_comms.leave_room(state, sid)


def register_server_events(state: MiddlewareState):
    """Register QKD server → middleware socket.io event handlers."""
    sc = state.server_client

    @sc.on('connect')
    def _server_connect():
        logger.info('Connected to QKD server.')

    @sc.on('disconnect')
    def _server_disconnect():
        logger.info('Disconnected from QKD server session WebSocket.')
        # NOTE: We do NOT stop media threads here.  The socketio.Client may
        # reconnect automatically after a transient network blip.  Media
        # threads are stopped explicitly by leave_room or /peer_disconnected.

    @sc.on('room-id')
    def _server_room_id(room_id):
        logger.info("room-id '%s' — starting media threads.", room_id)
        state.sio.emit('room-id', room_id)
        server_comms.start_video(state, room_id)
        server_comms.start_audio(state, room_id)

    @sc.on('frame')
    def _server_frame(data):
        if data.get('sender') is None:
            return  # echo of own frame; ignore
        frame = data.get('frame')
        if frame is not None:
            state.sio.emit('frame', {
                'frame':  frame,
                'width':  data.get('width', WIDTH),
                'height': data.get('height', HEIGHT),
                'self':   False,
            })

    @sc.on('audio-frame')
    def _server_audio_frame(data):
        if data.get('sender') is None:
            return  # echo of own audio; ignore
        audio = data.get('audio')
        if audio is not None:
            state.sio.emit('audio-frame', {
                'audio':       audio,
                'sample_rate': data.get('sample_rate', 8000),
                'self':        False,
            })


def register_rest_routes(state: MiddlewareState):
    """Register Flask REST routes that the QKD server calls."""
    flask_app = state.flask_app

    @flask_app.route('/peer_connection', methods=['POST'])
    def _rest_peer_connection():
        data = flask_request.get_json(force=True)
        peer_id = data.get('peer_id', '')
        ws_endpoint = data.get('socket_endpoint')
        session_id = data.get('session_id')
        logger.info('REST /peer_connection -- peer=%s ws=%s session=%s', peer_id, ws_endpoint, session_id)
        if ws_endpoint:
            # Spawn asynchronously so we return 200 immediately.
            # The QKD server's contact_client call has no timeout -- if we block
            # here waiting for the WebSocket handshake, the server stalls and
            # the calling peer's 10-second request timeout fires first.
            gevent.spawn(server_comms.connect_to_session_ws, state, ws_endpoint, peer_id, session_id=session_id)
        return jsonify({'status': 'ok'}), 200

    @flask_app.route('/peer_disconnected', methods=['POST'])
    def _rest_peer_disconnected():
        data = flask_request.get_json(force=True)
        peer_id = data.get('peer_id', '')
        logger.info('REST /peer_disconnected — peer=%s', peer_id)
        # Emit a dedicated event so the browser can cleanly reset session
        # state without marking the server as disconnected.
        state.sio.emit('peer-disconnected', {'peer_id': peer_id})
        if state.video_thread is not None:
            state.video_thread.stop()
            state.video_thread = None
        if state.audio_thread is not None:
            state.audio_thread.stop()
            state.audio_thread = None
        if state.server_client.connected:
            try:
                state.server_client.disconnect()
            except Exception:
                logger.debug('Ignoring error during server_client disconnect')
        return jsonify({'status': 'ok'}), 200
