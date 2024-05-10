from typing import Optional
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
logging.basicConfig(filename='logs/api.log', level=logging.DEBUG,
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

    # TODO: needed for flask, but is this the best way?
    app: Flask = Flask(__name__)
    logger: logging.Logger = None
    endpoint: Endpoint = None
    http_server: WSGIServer = None
    client = None

    @classmethod
    def init(cls, client, endpoint: Optional[Endpoint] = None):
        super().__init__(cls)
        cls.logger = logging.getLogger('ClientAPI')
        cls.state = APIState.NEW
        cls.client = client
        cls.instance = cls()

        # self.instance = None #TODO: what is this?
        # TODO: config file should have wifi or ad hoc mode

        cls.endpoint = endpoint if endpoint else Endpoint(
            '127.0.0.1', 4000)

        cls.logger.info(f"Created new ClientAPI{
                        f" at {cls.endpoint}" if endpoint else ""}")
        return cls.instance

    @classmethod
    def set_endpoint(cls, endpoint: Endpoint):
        cls.endpoint = endpoint
        cls.logger.info(f"Set ClintAPI endpoint to {cls.endpoint}")
        cls.state = APIState.INIT

    def run(self):
        cls = self.__class__
        cls.logger.info("Starting Client API.")
        if cls.state == APIState.NEW:
            raise Errors.SERVERERROR(
                "Cannot start API before initialization.")
        if cls.state == APIState.LIVE:
            raise Errors.SERVERERROR(
                "Cannot start API: already running.")

        # TODO: this is probably preventing clean teardown
        while True:
            try:
                # print(f"Serving Client API at {self.endpoint}.")
                cls.logger.info(f"Serving Client API at {cls.endpoint}.")

                cls.state = APIState.LIVE
                cls.http_server = WSGIServer(tuple(cls.endpoint), cls.app)
                cls.http_server.serve_forever()
            except OSError:
                print(f"Listener endpoint {cls.endpoint} in use.")
                cls.logger.error(f"Endpoint {cls.endpoint} in use.")

                cls.state = APIState.INIT
                cls.set_api_endpoint(
                    Endpoint(cls.endpoint.ip, cls.endpoint.port + 1))
                continue
            cls.logger.info("Client API terminated.")
            break

    def remove_last_period(text: str):
        return text[0:-1] if text[-1] == "." else text

    def authenticate(self, sess_token: str):
        if not self.sess_token == sess_token:
            raise Errors.BADAUTHENTICATION(
                f"Authentication failed for server with token '{sess_token}'.")

    def HandleExceptions(func: callable):
        """
        Decorator to handle commonly encountered exceptions in the Client API

        NOTE: This should never be called explicitly
        """
        def wrapper(*args, **kwargs):
            cls = ClientAPI
            try:
                return func(cls, *args, **kwargs)
            except Errors.BADAUTHENTICATION as e:
                return Errors.BADAUTHENTICATION.info(cls.remove_last_period(e))
            except Errors.BADREQUEST as e:
                return Errors.BADREQUEST.info(cls.remove_last_period(e))
            except Errors.SERVERERROR as e:
                return Errors.SERVERERROR.info(cls.remove_last_period(e))
            except Errors.BADGATEWAY as e:
                return Errors.BADGATEWAY.info(cls.remove_last_period(e))
            except Exception as e:
                return Errors.UNKNOWNERROR.info(cls.remove_last_period(e))

        # Makes it to trace is correct
        wrapper.__name__ = func.__name__
        return wrapper
    # endregion

    # region --- External 'Instance' Interface ---
    @classmethod
    def set_api_endpoint(cls, endpoint: Endpoint):
        cls.endpoint = endpoint
        cls.run()

    def kill(cls):
        cls.logger.info("Killing Client API.")
        if cls.state != APIState.LIVE:
            cls.logger.error(f"Cannot kill Client API when not {
                APIState.LIVE}.")
            return
        cls.http_server.stop()
        cls.state = APIState.INIT
    # endregion

    # region --- API Endpoints ---

    @app.route('/peer_connection', methods=['POST'])
    # @HandleExceptions
    # @HandleAuthentication
    def handle_peer_connection():
        """
        Receive incoming peer connection request.
        Poll client user. Instruct client to attempt socket
        connection to specified peer and self-identify with
        provided connection token.

        Request Parameters
        ------------------
        peer_id : str
        socket_endpoint : tuple
        conn_token : string
        """
        cls = ClientAPI
        sess_token, peer_id, socket_endpoint, conn_token = get_parameters(
            request.json, 'sess_token', 'peer_id', 'socket_endpoint', 'conn_token')
        cls.authenticate(sess_token)
        socket_endpoint = Endpoint(*socket_endpoint)
        cls.logger.info(f"Instructied to connect to peer {peer_id} at {
            socket_endpoint} with token '{conn_token}'.")

        try:
            res = cls.client.handle_peer_connection(
                peer_id, socket_endpoint, conn_token)
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
