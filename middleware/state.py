"""MiddlewareState — Single mutable state container for the middleware.

Replaces scattered module-level globals with a single, inspectable object.
"""
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so ``shared.*`` imports work.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import socketio
from flask import Flask
from flask_cors import CORS

from shared.logging import get_logger

from shared import find_available_port

logger = get_logger(__name__)

WIDTH  = 640
HEIGHT = 480

DEFAULT_SERVER_HOST = os.environ.get("QUANTUM_SERVER_HOST", "127.0.0.1")
DEFAULT_SERVER_PORT = int(os.environ["QUANTUM_SERVER_PORT"]) if os.environ.get("QUANTUM_SERVER_PORT") else 0
IS_LOCAL = os.environ.get("QVC_AUTO_CONNECT", "").lower() in ("1", "true", "yes")


class MiddlewareState:
    """Holds all mutable runtime state for the middleware process."""

    def __init__(self):
        """Initialize all middleware runtime state."""
        logger.debug("MiddlewareState.__init__ starting")

        # ── Socket.io server (browsers connect here) ─────────────────────
        _dir = Path(__file__).parent
        self.flask_app = Flask(__name__,
                               template_folder=str(_dir / "templates"),
                               static_folder=str(_dir / "static"))
        import re
        _cors_raw = os.environ.get("QVC_CORS_ORIGINS", "http://localhost:*,https://localhost:*,https://andypeterson.dev")
        _cors_list = [o.strip() for o in _cors_raw.split(",")]
        logger.debug("CORS origins (raw): %s", _cors_list)
        CORS(self.flask_app, origins=_cors_list)

        # python-socketio doesn't support glob patterns — use a callable
        # that matches any localhost/127.0.0.1 origin on any port
        _localhost_re = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")
        _extra_origins = {o for o in _cors_list if not o.endswith(":*")}

        def _check_origin(origin):
            return _localhost_re.match(origin) is not None or origin in _extra_origins

        logger.debug("Socket.IO CORS: localhost any-port + %s", _extra_origins)
        self.sio = socketio.Server(
            cors_allowed_origins=_check_origin,
            async_mode="gevent",
            logger=False,
            engineio_logger=False,
        )
        self.app = socketio.WSGIApp(self.sio, self.flask_app)

        # ── Socket.io client (connects to QKD server session WebSocket) ──
        self.server_client = socketio.Client(logger=False, engineio_logger=False)

        # ── QKD server address ───────────────────────────────────────────
        self.server_host: str = ""
        self.server_port: int = 0
        self.server_alive: bool = False

        # ── Identity ─────────────────────────────────────────────────────
        self.user_id: str = ""
        self.middleware_port: int = 0

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

        logger.debug("MiddlewareState initialized  server=%s:%s  isLocal=%s",
                      DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, IS_LOCAL)

    def server_url(self, path: str) -> str:
        """Build a full URL for the QKD server's REST API."""
        from shared.ssl_utils import get_ssl_context  # noqa: PLC0415
        scheme = "https" if get_ssl_context() else "http"
        return f"{scheme}://{self.server_host}:{self.server_port}{path}"
