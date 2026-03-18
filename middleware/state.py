"""
MiddlewareState — Single mutable state container for the middleware.

Replaces scattered module-level globals with a single, inspectable object.
"""
import os
import socketio
from flask import Flask


MIDDLEWARE_PORT = 5001
WIDTH  = 640
HEIGHT = 480

DEFAULT_SERVER_HOST = os.environ.get('QUANTUM_SERVER_HOST', '192.168.1.28')
DEFAULT_SERVER_PORT = int(os.environ.get('QUANTUM_SERVER_PORT', '5050'))
IS_LOCAL = DEFAULT_SERVER_HOST != ''


class MiddlewareState:
    """Holds all mutable runtime state for the middleware process."""

    def __init__(self):
        # ── Socket.io server (browsers connect here) ─────────────────────
        self.flask_app = Flask(__name__)
        self.sio = socketio.Server(
            cors_allowed_origins='*',
            async_mode='gevent',
            logger=False,
            engineio_logger=False,
        )
        self.app = socketio.WSGIApp(self.sio, self.flask_app)

        # ── Socket.io client (connects to QKD server session WebSocket) ──
        self.server_client = socketio.Client(logger=False, engineio_logger=False)

        # ── QKD server address ───────────────────────────────────────────
        self.server_host: str = ''
        self.server_port: int = 0
        self.server_alive: bool = False

        # ── Identity ─────────────────────────────────────────────────────
        self.user_id: str = ''
        self.middleware_port: int = MIDDLEWARE_PORT

        # ── Video ────────────────────────────────────────────────────────
        self.video_thread = None
        self.camera_enabled: bool = True
        self.camera_device: int = 0

        # ── Audio ────────────────────────────────────────────────────────
        self.audio_thread = None
        self.muted: bool = False
        self.audio_device: int = 0

        # ── Health checks ────────────────────────────────────────────────
        self.health_greenlet = None

    def server_url(self, path: str) -> str:
        """Build a full URL for the QKD server's REST API."""
        return f'http://{self.server_host}:{self.server_port}{path}'
