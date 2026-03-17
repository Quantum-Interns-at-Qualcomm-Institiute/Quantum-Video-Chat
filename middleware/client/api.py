from enum import Enum
from flask import Flask, jsonify, request
from functools import total_ordering, wraps
from gevent.pywsgi import WSGIServer  # For asynchronous handling
from threading import Thread

from client.errors import Errors
from client.endpoint import Endpoint
from client.util import get_parameters
from shared.config import LOCAL_IP, CLIENT_API_PORT
from custom_logging import logger


# region --- Utils ---


@total_ordering
class APIState(Enum):
    NEW = 'NEW'
    INIT = 'INIT'
    LIVE = 'LIVE'

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented
# endregion


def _handle_exceptions(fn):
    """Decorator to handle commonly encountered exceptions in the Client API."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Errors.BADAUTHENTICATION.value as e:
            return Errors.BADAUTHENTICATION.value.info(_remove_last_period(e))
        except Errors.BADREQUEST.value as e:
            return Errors.BADREQUEST.value.info(_remove_last_period(e))
        except Errors.SERVERERROR.value as e:
            return Errors.SERVERERROR.value.info(_remove_last_period(e))
        except Errors.BADGATEWAY.value as e:
            return Errors.BADGATEWAY.value.info(_remove_last_period(e))
        except Exception as e:
            return Errors.UNKNOWNERROR.value.info(_remove_last_period(e))
    return wrapper


def _remove_last_period(text):
    text = str(text)
    return text[0:-1] if text[-1] == "." else text


# region --- Client API ---


class ClientAPI:
    """Client-side REST API for receiving peer connection notifications.

    Uses composition (owns a Thread) rather than inheriting from Thread,
    so the class can be extended without coupling to threading internals.
    """
    DEFAULT_ENDPOINT = Endpoint(LOCAL_IP, CLIENT_API_PORT)

    def __init__(self, client, endpoint=None):
        self._thread = None
        self.app = Flask(__name__)
        self.http_server = None
        self.client = client
        self.endpoint = endpoint or client.api_endpoint
        self.state = APIState.INIT
        self._register_routes()

        logger.info(f"Initializing Client API with endpoint {self.endpoint}.")

    def _register_routes(self):
        self.app.add_url_rule(
            '/peer_connection', 'handle_peer_connection',
            _handle_exceptions(self._handle_peer_connection), methods=['POST'])
        self.app.add_url_rule(
            '/peer_disconnected', 'handle_peer_disconnected',
            _handle_exceptions(self._handle_peer_disconnected), methods=['POST'])

    # region --- Thread delegation ---

    def start(self):
        """Launch the REST API on a background daemon thread."""
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def is_alive(self):
        """Return True if the background thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout=None):
        """Block until the background thread terminates."""
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    # endregion

    # region --- External Interface ---

    def run(self):
        """Public alias for backward compatibility (e.g. tests calling api.run())."""
        return self._run()

    def _run(self):
        logger.info("Starting Client API.")
        if self.state == APIState.NEW:
            raise Errors.SERVERERROR.value(
                "Cannot start API before initialization.")
        if self.state == APIState.LIVE:
            raise Errors.SERVERERROR.value(
                "Cannot start API: already running.")

        while True:
            try:
                logger.info(f"Serving Client API at {self.endpoint}.")
                self.state = APIState.LIVE
                self.http_server = WSGIServer(tuple(self.endpoint), self.app)
                self.http_server.serve_forever()
            except OSError as e:
                logger.error(f"Endpoint {self.endpoint} in use.")
                self.state = APIState.INIT
                self.client.set_api_endpoint(
                    Endpoint(self.endpoint.ip, self.endpoint.port + 1))
                self.endpoint = self.client.api_endpoint
                continue
            logger.info("Client API terminated.")
            break

    def kill(self):
        logger.info("Killing Client API.")
        if self.state != APIState.LIVE:
            logger.error(f"Cannot kill Client API when not {APIState.LIVE}.")
            return
        self.http_server.stop()
        self.state = APIState.INIT

    # endregion

    # region --- API Endpoints ---

    def _handle_peer_connection(self):
        """
        Receive incoming peer connection request.
        Poll client user. Instruct client to attempt socket
        connection to specified peer and self-identify with
        provided connection token.

        Request Parameters
        ------------------
        peer_id : str
        socket_endpoint : tuple
        session_settings : dict (optional) — host's shared settings
        """
        peer_id, socket_endpoint = get_parameters(
            request.json, 'peer_id', 'socket_endpoint')
        session_settings = request.json.get('session_settings')
        socket_endpoint = Endpoint(*socket_endpoint)
        logger.info(f"Instructed to connect to peer {peer_id} at {socket_endpoint}.")

        try:
            res = self.client.handle_peer_connection(
                peer_id, socket_endpoint, session_settings=session_settings)
        except Exception as e:
            logger.info(e)
            return jsonify({"error_code": "500",
                            "error_message": "Internal Server Error",
                            "details": "Connection failed"}), 500

        logger.info("client.handle_peer_connection() finished.")
        if not res:
            logger.info("Responding with 418")
            return jsonify({"error_code": "418",
                            "error_message": "I'm a teapot",
                            "details": "Peer User refused connection"}), 418
        logger.info("Responding with 200")
        return jsonify({'status_code': '200'}), 200

    def _handle_peer_disconnected(self):
        """
        Receive notification that peer has disconnected from the call.

        Request Parameters
        ------------------
        peer_id : str
        """
        (peer_id,) = get_parameters(request.json, 'peer_id')
        logger.info(f"Received peer disconnect notification for peer {peer_id}.")
        self.client.handle_peer_disconnected(peer_id)
        return jsonify({'status': 'ok'}), 200

    # endregion

    # region --- Backward Compatibility ---

    @classmethod
    def init(cls, client):
        """Deprecated: use ClientAPI(client) directly."""
        instance = cls(client)
        return instance

    @staticmethod
    def remove_last_period(text: str):
        return _remove_last_period(text)

    # endregion

# endregion
