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

    # TODO: needed for flask, but is this the best way?
    app: Flask = Flask(__name__)

    def __init__(self, endpoint: Optional[Endpoint] = None):
        super().__init__()
        self.logger = logging.getLogger('ClientAPI')
        self.state = APIState.INIT

        self.http_server: WSGIServer = None
        # self.instance = None #TODO: what is this?

        # TODO: config file should have wifi or ad hoc mode

        self.endpoint: Endpoint = endpoint if endpoint else Endpoint(
            '127.0.0.1', 4000)

        self.logger.info(f"Created new ClientAPI at {self.endpoint}")

    @classmethod
    def verify_server(cls, sess_token):
        if type(sess_token) is str:
            return True
        raise Errors.BADAUTHENTICATION(f"Unrecognized session token '{
                                       sess_token}' from server.")

    def remove_last_period(text: str):
        return text[0:-1] if text[-1] == "." else text

    def HandleAuthentication(endpoint_handler):
        """
        Decorator to handle authentication for server.

        NOTE: Assumes `cls` has been passed by @HandleExceptions
        NOTE: This should never be called explicitly

        Parameters
        ----------
        sess_token : str
        """
        def handler_with_authentication(cls, *args, **kwargs):
            sess_token, = get_parameters(request.json, 'sess_token')
            if not cls.verify_server(sess_token):
                raise Errors.BADAUTHENTICATION(
                    f"Authentication failed for server with token '{sess_token}'.")

            return endpoint_handler(cls, *args, **kwargs)
        handler_with_authentication.__name__ = endpoint_handler.__name__
        return handler_with_authentication

    def HandleExceptions(endpoint_handler):
        """
        Decorator to handle commonly encountered exceptions in the Client API

        NOTE: This should never be called explicitly
        """
        def handler_with_exceptions(*args, **kwargs):
            cls = ClientAPI
            try:
                return endpoint_handler(cls, *args, **kwargs)
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
        handler_with_exceptions.__name__ = endpoint_handler.__name__
        return handler_with_exceptions
    # endregion

    # region --- External 'Instance' Interface ---

    def run(self):
        cls = self.__class__

        self.logger.info("Starting Client API.")
        if self.state == APIState.NEW:
            raise Errors.SERVERERROR(
                "Cannot start API before initialization.")
        if self.state == APIState.LIVE:
            raise Errors.SERVERERROR(
                "Cannot start API: already running.")

        while True:
            try:
                print(f"Serving Client API at {self.endpoint}.")
                self.logger.info(f"Serving Client API at {self.endpoint}.")

                self.state = APIState.LIVE
                self.http_server = WSGIServer(tuple(self.endpoint), self.app)
                self.http_server.serve_forever()
            except OSError as e:
                print(f"Listener endpoint {cls.endpoint} in use.")
                self.logger.error(f"Endpoint {cls.endpoint} in use.")

                self.state = APIState.INIT
                cls.client.set_api_endpoint(
                    Endpoint(cls.endpoint.ip, cls.endpoint.port + 1))
                continue
            self.logger.info("Client API terminated.")
            break

    @classmethod
    def kill(cls):
        self.logger.info("Killing Client API.")
        if self.state != APIState.LIVE:
            self.logger.error(f"Cannot kill Client API when not {
                APIState.LIVE}.")
            return
        cls.http_server.stop()
        self.state = APIState.INIT
    # endregion

    # region --- API Endpoints ---

    @app.route('/peer_connection', methods=['POST'])
    @HandleExceptions
    @HandleAuthentication
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
        conn_token : string
        """
        peer_id, socket_endpoint, conn_token = get_parameters(
            request.json, 'peer_id', 'socket_endpoint', 'conn_token')
        socket_endpoint = Endpoint(*socket_endpoint)
        self.logger.info(f"Instructied to connect to peer {peer_id} at {
            socket_endpoint} with token '{conn_token}'.")

        try:
            res = cls.client.handle_peer_connection(
                peer_id, socket_endpoint, conn_token)
        except Exception as e:
            # TODO: Why did the connection fail?
            # TODO: Move into init
            self.logger.info(e)
            return jsonify({"error_code": "500",
                            "error_message": "Internal Server Error",
                            "details": "Connectioned failed"}), 500

        self.logger.info("client.handle_peer_connection() finished.")
        if not res:
            # User Refused
            logger.info("Responding with 418")
            return jsonify({"error_code": "418",
                            "error_message": "I'm a teapot",
                            "details": "Peer User refused connection"}), 418
        # TODO: What should we return?
        self.logger.info("Responding with 200")
        return jsonify({'status_code': '200'}), 200
    # endregion
# endregion
