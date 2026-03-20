import logging
import time
from collections import defaultdict
from functools import wraps

from flask import Flask, jsonify, request
from gevent.pywsgi import WSGIServer

from server import Server
from state import APIState
from utils import (
    ServerError, get_parameters, Endpoint,
)


class RateLimiter:
    """Simple in-memory rate limiter using a sliding window."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        timestamps = self._requests[key]
        # Prune old entries
        self._requests[key] = [t for t in timestamps if now - t < self.window]
        if len(self._requests[key]) >= self.max_requests:
            return False
        self._requests[key].append(now)
        return True


_rate_limiter = RateLimiter()


def rate_limit(f):
    """Decorator that enforces rate limiting per client IP."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        client_ip = request.remote_addr or 'unknown'
        if not _rate_limiter.is_allowed(client_ip):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        return f(*args, **kwargs)
    return wrapper


def _get_ssl_context():
    """Return (cert, key) paths if dev certs exist, else None."""
    import os
    from pathlib import Path
    for d in [
        Path(os.environ.get("DEV_CERT_DIR", "")),
        Path(__file__).resolve().parents[2] / ".certs",
    ]:
        cert, key = d / "cert.pem", d / "key.pem"
        if cert.is_file() and key.is_file():
            return (str(cert), str(key))
    return None
from admin_routes import admin_bp, init_admin
from shared.config import LOCAL_IP, SERVER_REST_PORT
from shared.decorators import handle_exceptions_with_cls


class ServerAPI:
    DEFAULT_ENDPOINT = Endpoint(LOCAL_IP, SERVER_REST_PORT)

    app = Flask(__name__)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.register_blueprint(admin_bp)

    http_server = None
    server = None
    endpoint = None
    state = APIState.INIT

    logger = logging.getLogger('ServerAPI')

    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    # Shared exception-handling decorator that injects ``cls = ServerAPI``
    HandleExceptions = handle_exceptions_with_cls(lambda: ServerAPI)

    @classmethod
    def init(cls, server: Server):
        cls.logger.info(f"Initializing Server API with endpoint {server.api_endpoint}.")
        if cls.state == APIState.LIVE:
            raise ServerError("Cannot reconfigure API during server runtime.")
        cls.server = server
        cls.endpoint = server.api_endpoint
        cls.state = APIState.IDLE
        # Inject server into admin blueprint
        init_admin(server, lambda: cls.state, shutdown_fn=cls.graceful_shutdown)

    @classmethod
    def start(cls):
        cls.logger.info(f"Starting Server API at {cls.endpoint}.")
        if cls.state == APIState.INIT:
            raise ServerError("Cannot start API before initialization.")
        if cls.state == APIState.LIVE:
            raise ServerError("Cannot start API: already running.")
        cls.state = APIState.LIVE
        ssl_ctx = _get_ssl_context()
        ssl_args = {"certfile": ssl_ctx[0], "keyfile": ssl_ctx[1]} if ssl_ctx else {}
        cls.http_server = WSGIServer(tuple(cls.endpoint), cls.app, **ssl_args)
        cls.http_server.serve_forever()

    @classmethod
    def kill(cls):
        cls.logger.info("Killing Server API.")
        if cls.state != APIState.LIVE:
            raise ServerError(f"Cannot kill Server API when not {APIState.LIVE}.")
        cls.http_server.stop()
        cls.state = APIState.IDLE

    @classmethod
    def graceful_shutdown(cls):
        """Stop the WebSocket API, then the REST API. Safe to call from any context."""
        cls.logger.info("Initiating graceful shutdown...")

        # Stop WebSocket API if running
        if cls.server is not None:
            ws = getattr(cls.server, 'websocket_instance', None)
            if ws is not None:
                try:
                    if ws.is_alive():
                        ws.kill()
                        ws.join(timeout=3)
                except Exception as e:
                    cls.logger.warning(f"Error stopping WebSocket API: {e}")

        # Stop REST API
        try:
            cls.kill()
        except Exception as e:
            cls.logger.warning(f"Error stopping REST API: {e}")

    # region --- API Endpoints ---

    @app.route('/create_user', methods=['POST'])
    @rate_limit
    @HandleExceptions
    def create_user(cls):
        """Create and store a user with unique user_id. Returns user_id."""
        (api_endpoint,) = get_parameters(request.json, 'api_endpoint')
        user_id = cls.server.add_user(api_endpoint)
        cls.logger.info(f"Created a user with ID: {user_id}")
        return jsonify({'user_id': user_id}), 200

    @app.route('/peer_connection', methods=['POST'])
    @rate_limit
    @HandleExceptions
    def handle_peer_connection(cls):
        """Instruct peer to connect to user's provided socket endpoint."""
        user_id, peer_id = get_parameters(request.json, 'user_id', 'peer_id')
        session_settings = request.json.get('session_settings')
        cls.logger.info(f"Received request from User {user_id} to connect with User {peer_id}.")
        endpoint = cls.server.handle_peer_connection(user_id, peer_id, session_settings=session_settings)
        return jsonify({'socket_endpoint': tuple(endpoint)}), 200

    @app.route('/disconnect_peer', methods=['POST'])
    @rate_limit
    @HandleExceptions
    def disconnect_peer(cls):
        """Disconnect a user from their active peer session."""
        (user_id,) = get_parameters(request.json, 'user_id')
        cls.server.disconnect_peer(user_id)
        cls.logger.info(f"Disconnected user {user_id} from peer.")
        return jsonify({'status': 'disconnected', 'user_id': user_id}), 200

    @app.route('/remove_user', methods=['POST', 'DELETE'])
    @rate_limit
    @HandleExceptions
    def remove_user(cls):
        """Remove a user from the server's user store on client shutdown."""
        (user_id,) = get_parameters(request.json, 'user_id')
        cls.server.remove_user(user_id)
        cls.logger.info(f"Removed user with ID: {user_id}")
        return jsonify({'status': 'removed', 'user_id': user_id}), 200

    # endregion
