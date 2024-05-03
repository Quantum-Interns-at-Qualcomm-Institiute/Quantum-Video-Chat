import psutil
import platform
from functools import total_ordering
from enum import Enum
from client.errors import Errors
from client.endpoint import Endpoint
from client.util import get_parameters
from flask import Flask, jsonify, request
from threading import Thread
from gevent.pywsgi import WSGIServer  # For asynchronous handling


# region --- Logging ---
import logging
logging.basicConfig(filename='src/middleware/logs/api.log', level=logging.DEBUG,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
# endregion


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


# region --- Client API ---


class ClientAPI(Thread):
    # Try to get default en0 address to start client API endpoint on
    key = 'WiFi 2' if platform.system() == 'Windows' else 'en0'

    for prop in psutil.net_if_addrs()[key]:
        if prop.family == 2:
            ip = prop.address

    DEFAULT_ENDPOINT = Endpoint(ip if ip else '127.0.0.1', 4000)

    app = Flask(__name__)
    http_server = None
    client = None
    endpoint = None
    state = APIState.NEW

    instance = None

    # region --- Utils ---
    logger = logging.getLogger('ClientAPI')

    def remove_last_period(text: str):
        return text[0:-1] if text[-1] == "." else text

    def HandleExceptions(endpoint_handler):
        """
        Decorator to handle commonly encountered exceptions in the Client API

        NOTE: This should never be called explicitly
        """
        def handler_with_exceptions(*args, **kwargs):
            cls = ClientAPI
            try:
                return endpoint_handler(cls, *args, **kwargs)
            except Errors.BADAUTHENTICATION.value as e:
                return Errors.BADAUTHENTICATION.value.info(cls.remove_last_period(e))
            except Errors.BADREQUEST.value as e:
                return Errors.BADREQUEST.value.info(cls.remove_last_period(e))
            except Errors.SERVERERROR.value as e:
                return Errors.SERVERERROR.value.info(cls.remove_last_period(e))
            except Errors.BADGATEWAY.value as e:
                return Errors.BADGATEWAY.value.info(cls.remove_last_period(e))
            except Exception as e:
                return Errors.UNKNOWNERROR.value.info(cls.remove_last_period(e))

        # Makes it to trace is correct
        handler_with_exceptions.__name__ = endpoint_handler.__name__
        return handler_with_exceptions
    # endregion

    # region --- External 'Instance' Interface ---

    @classmethod
    def init(cls, client):
        cls.logger.info(f"Initializing Client API with endpoint {client.api_endpoint}.")
        if cls.state == APIState.LIVE:
            raise Errors.SERVERERROR.value(
                "Cannot reconfigure API during server runtime.")

        cls.client = client
        cls.endpoint = client.api_endpoint
        cls.state = APIState.INIT
        cls.instance = cls()
        return cls.instance

    def run(self):
        cls = self.__class__

        cls.logger.info("Starting Client API.")
        if cls.state == APIState.NEW:
            raise Errors.SERVERERROR.value(
                "Cannot start API before initialization.")
        if cls.state == APIState.LIVE:
            raise Errors.SERVERERROR.value(
                "Cannot start API: already running.")

        while True:
            try:
                print(f"Serving Client API at {cls.endpoint}.")
                cls.logger.info(f"Serving Client API at {cls.endpoint}.")

                cls.state = APIState.LIVE
                cls.http_server = WSGIServer(tuple(cls.endpoint), cls.app)
                cls.http_server.serve_forever()
            except OSError as e:
                print(f"Listener endpoint {cls.endpoint} in use.")
                cls.logger.error(f"Endpoint {cls.endpoint} in use.")

                cls.state = APIState.INIT
                cls.client.set_api_endpoint(
                    Endpoint(cls.endpoint.ip, cls.endpoint.port + 1))
                continue
            cls.logger.info("Client API terminated.")
            break

    @classmethod
    def kill(cls):
        cls.logger.info("Killing Client API.")
        if cls.state != APIState.LIVE:
            cls.logger.error(f"Cannot kill Client API when not {APIState.LIVE}.")
            return
        cls.http_server.stop()
        cls.state = APIState.INIT
    # endregion

    # region --- API Endpoints ---

    @app.route('/peer_connection', methods=['POST'])
    @HandleExceptions
    def handle_peer_connection(cls):
        """
        Receive incoming peer connection request.
        Poll client user. Instruct client to attempt socket
        connection to specified peer and self-identify with
        provided connection token.

        Request Parameters
        ------------------
        peer_id : str
        socket_endpoint : tuple
        """
        peer_id, socket_endpoint = get_parameters(
            request.json, 'peer_id', 'socket_endpoint')
        socket_endpoint = Endpoint(*socket_endpoint)
        cls.logger.info(f"Instructied to connect to peer {peer_id} at {socket_endpoint}.")

        try:
            res = cls.client.handle_peer_connection(
                peer_id, socket_endpoint)
        except Exception as e:
            # TODO: Why did the connection fail?
            # TODO: Move into init
            cls.logger.info(e)
            return jsonify({"error_code": "500",
                            "error_message": "Internal Server Error",
                            "details": "Connectioned failed"}), 500

        cls.logger.info("client.handle_peer_connection() finished.")
        if not res:
            # User Refused
            logger.info("Responding with 418")
            return jsonify({"error_code": "418",
                            "error_message": "I'm a teapot",
                            "details": "Peer User refused connection"}), 418
        # TODO: What should we return?
        cls.logger.info("Responding with 200")
        return jsonify({'status_code': '200'}), 200
    # endregion
# endregion
