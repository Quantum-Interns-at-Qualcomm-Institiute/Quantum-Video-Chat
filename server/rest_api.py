"""REST API for the QKD server."""

import logging
import os
import threading
import time
from collections import defaultdict
from functools import wraps

from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from state import APIState
from utils import (
    Endpoint,
    ServerError,
    get_parameters,
)

from server import Server
from shared.logging import get_logger

_logger = get_logger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter using a sliding window."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        """Initialize rate limiter with request cap and time window."""
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Return True if the key has not exceeded the rate limit."""
        now = time.time()
        with self._lock:
            timestamps = self._requests[key]
            self._requests[key] = [t for t in timestamps if now - t < self.window]
            if not self._requests[key]:
                del self._requests[key]
            if len(self._requests.get(key, [])) >= self.max_requests:
                _logger.warning("Rate limit exceeded for %s", key)
                return False
            self._requests[key].append(now)
            return True


_rate_limiter = RateLimiter()


def rate_limit(f):
    """Decorator that enforces rate limiting per client IP."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        client_ip = request.remote_addr or "unknown"
        if not _rate_limiter.is_allowed(client_ip):
            return jsonify({"error": "Rate limit exceeded"}), 429
        return f(*args, **kwargs)
    return wrapper


from admin_routes import admin_bp, init_admin

from shared.config import LOCAL_IP, SERVER_REST_PORT
from shared.decorators import handle_exceptions_with_cls
from shared.ssl_utils import get_ssl_context as _get_ssl_context


class ServerAPI:
    """Flask-based REST API for QKD server management."""

    DEFAULT_ENDPOINT = Endpoint(LOCAL_IP, SERVER_REST_PORT)

    app = Flask(__name__)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.register_blueprint(admin_bp)

    socketio = None
    server = None
    endpoint = None
    state = APIState.INIT

    logger = logging.getLogger("ServerAPI")

    _allowed_origins = [  # noqa: RUF012
        o.strip() for o in
        os.environ.get("QVC_CORS_ORIGINS", "http://localhost:*,https://localhost:*,https://andypeterson.dev").split(",")
    ]

    @app.after_request
    def add_cors_headers(self):
        """Add CORS headers to every response."""
        import fnmatch
        origin = request.headers.get("Origin", "")
        if any(fnmatch.fnmatch(origin, pat) for pat in ServerAPI._allowed_origins):
            self.headers["Access-Control-Allow-Origin"] = origin
        else:
            if origin:
                _logger.debug("CORS rejected origin: %s", origin)
        self.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        self.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return self

    # Shared exception-handling decorator that injects ``cls = ServerAPI``
    HandleExceptions = handle_exceptions_with_cls(lambda: ServerAPI)

    @classmethod
    def init_socketio(cls):
        """Create the shared SocketIO instance (must be called before Server construction)."""
        if cls.socketio is None:
            # Expand glob patterns for python-socketio (it only does exact matching)
            sio_origins = []
            for o in cls._allowed_origins:
                if o.endswith(":*"):
                    prefix = o[:-1]
                    sio_origins.extend(prefix + str(p) for p in [3000, 4321, 5001, 5002, 5003, 5050, 8000, 8080])
                else:
                    sio_origins.append(o)
            _logger.debug("SocketIO CORS origins (expanded): %s", sio_origins)
            cls.socketio = SocketIO(cls.app, cors_allowed_origins=sio_origins, async_mode="gevent")
            _logger.debug("SocketIO initialized")

    @classmethod
    def init(cls, server: Server):
        """Configure the API with a Server instance."""
        cls.logger.info("Initializing Server API with endpoint %s.", server.api_endpoint)
        if cls.state == APIState.LIVE:
            msg = "Cannot reconfigure API during server runtime."
            raise ServerError(msg)
        cls.init_socketio()
        cls.server = server
        cls.endpoint = server.api_endpoint
        cls.state = APIState.IDLE
        # Inject server into admin blueprint
        init_admin(server, lambda: cls.state, shutdown_fn=cls.graceful_shutdown)

    @classmethod
    def start(cls):
        """Start the Flask server."""
        cls.logger.info("Starting Server API at %s.", cls.endpoint)
        if cls.state == APIState.INIT:
            msg = "Cannot start API before initialization."
            raise ServerError(msg)
        if cls.state == APIState.LIVE:
            msg = "Cannot start API: already running."
            raise ServerError(msg)
        cls.state = APIState.LIVE
        ssl_ctx = _get_ssl_context()
        ssl_args = {"certfile": ssl_ctx[0], "keyfile": ssl_ctx[1]} if ssl_ctx else {}
        cls.socketio.run(cls.app, host=cls.endpoint.ip, port=cls.endpoint.port, **ssl_args)

    @classmethod
    def kill(cls):
        """Stop the running server."""
        cls.logger.info("Killing Server API.")
        if cls.state != APIState.LIVE:
            msg = f"Cannot kill Server API when not {APIState.LIVE}."
            raise ServerError(msg)
        cls.socketio.stop()
        cls.state = APIState.IDLE

    @classmethod
    def graceful_shutdown(cls):
        """Stop the server. Safe to call from any context."""
        cls.logger.info("Initiating graceful shutdown...")

        # Stop the combined REST + WebSocket API
        try:
            cls.kill()
        except (ServerError, RuntimeError) as e:
            cls.logger.warning("Error stopping Server API: %s", e)

    # region --- API Endpoints ---

    @app.route("/create_user", methods=["POST"])
    @rate_limit
    @HandleExceptions
    def create_user(self):
        """Create and store a user with unique user_id. Returns user_id."""
        _logger.debug("POST /create_user  body=%s", request.json)
        (api_endpoint,) = get_parameters(request.json, "api_endpoint")
        user_id = self.server.add_user(api_endpoint)
        _logger.info("POST /create_user -> user_id=%s  endpoint=%s", user_id, api_endpoint)
        return jsonify({"user_id": user_id}), 200

    @app.route("/peer_connection", methods=["POST"])
    @rate_limit
    @HandleExceptions
    def handle_peer_connection(self):
        """Instruct peer to connect to user's provided socket endpoint."""
        user_id, peer_id = get_parameters(request.json, "user_id", "peer_id")
        session_settings = request.json.get("session_settings")
        _logger.info("POST /peer_connection  user=%s -> peer=%s  settings=%s",
                      user_id, peer_id, session_settings)
        endpoint, session_id = self.server.handle_peer_connection(
            user_id, peer_id, session_settings=session_settings,
        )
        _logger.info("POST /peer_connection -> ws=%s  session=%s", endpoint, session_id)
        return jsonify({"socket_endpoint": tuple(endpoint), "session_id": session_id}), 200

    @app.route("/disconnect_peer", methods=["POST"])
    @rate_limit
    @HandleExceptions
    def disconnect_peer(self):
        """Disconnect a user from their active peer session."""
        (user_id,) = get_parameters(request.json, "user_id")
        _logger.info("POST /disconnect_peer  user=%s", user_id)
        self.server.disconnect_peer(user_id)
        _logger.debug("POST /disconnect_peer -> done  user=%s", user_id)
        return jsonify({"status": "disconnected", "user_id": user_id}), 200

    @app.route("/remove_user", methods=["POST", "DELETE"])
    @rate_limit
    @HandleExceptions
    def remove_user(self):
        """Remove a user from the server's user store on client shutdown."""
        (user_id,) = get_parameters(request.json, "user_id")
        _logger.info("POST /remove_user  user=%s", user_id)
        self.server.remove_user(user_id)
        _logger.debug("POST /remove_user -> done  user=%s", user_id)
        return jsonify({"status": "removed", "user_id": user_id}), 200

    # endregion
