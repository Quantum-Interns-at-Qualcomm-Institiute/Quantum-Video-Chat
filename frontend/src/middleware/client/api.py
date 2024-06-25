from client.endpoint import Endpoint
from client.errors import Errors
from client.util import APIState, get_parameters, remove_last_period
from flask import Flask, jsonify, request
from threading import Thread
from gevent.pywsgi import WSGIServer  # For asynchronous handling

import logging
logging.basicConfig(filename='logs/api.log', level=logging.DEBUG,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


# TODO:Thread is needed for flask, but is this the best way?
class ClientAPI(Thread):
    logger: logging.Logger = logging.getLogger('ClientAPI')
    client_api_state = APIState.NEW

    app: Flask = Flask(__name__)
    client = None
    instance = None
    endpoint: Endpoint = None
    http_server: WSGIServer = None

    @classmethod
    def init(cls, client, endpoint: Endpoint):
        super().__init__(cls)
        cls.client = client
        cls.instance = cls()
        cls.endpoint = endpoint
        cls.http_server = WSGIServer(tuple(cls.endpoint), cls.app)

        cls.logger.info(f"Initialized new ClientAPI with {cls.endpoint}")
        cls.set_state(APIState.INITIALIZED)
        return cls.instance

    @classmethod
    def set_state(cls, new_state: APIState):
        old_state = cls.client_api_state
        if old_state > new_state:
            raise Errors.INTERNALCLIENTERROR(f"Cannot set state back to {new_state} or {cls.client_api_state}")
        if cls.client_api_state == new_state:
            raise Errors.INTERNALCLIENTERROR(f"State already set to {new_state}")
        cls.client_api_state = new_state
        cls.logger.info(f"ClientAPI's state moved from {old_state} to {new_state}")

    @classmethod
    def run(cls):
        cls.logger.info("Starting ClientAPI...")

        if cls.client_api_state == APIState.NEW:
            raise Errors.SERVERERROR("Cannot start API before initialization.")
        if cls.client_api_state == APIState.LIVE:
            raise Errors.SERVERERROR("Cannot start API: already running.")

        # TODO: this is probably preventing clean teardown
        while True:
            try:
                cls.set_state(APIState.LIVE)
                cls.logger.info(f"Serving Client API at {cls.endpoint}.")
                cls.http_server.serve_forever()
            except OSError:
                raise BaseException(f"Listener endpoint {cls.endpoint} in use.")
                # TODO: determine if desired behavior is to adapt (like below) or make the user figure it out
                # cls.logger.error(f"Endpoint {cls.endpoint} in use.")

                # cls.client_api_state = APIState.INIT
                # cls.set_api_endpoint(
                #     Endpoint(cls.endpoint.ip, cls.endpoint.port + 1))
                # continue
            cls.logger.info("Client API terminated.")
            break

    @classmethod
    def authenticate(cls, sess_token: str):
        if not cls.client.sess_token == sess_token:
            raise Errors.BADAUTHENTICATION(f"Authentication failed for server with token '{sess_token}'.")

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
                return Errors.BADAUTHENTICATION.info(remove_last_period(e))
            except Errors.BADREQUEST as e:
                return Errors.BADREQUEST.info(remove_last_period(e))
            except Errors.SERVERERROR as e:
                return Errors.SERVERERROR.info(remove_last_period(e))
            except Errors.BADGATEWAY as e:
                return Errors.BADGATEWAY.info(remove_last_period(e))
            except Exception as e:
                return Errors.UNKNOWNERROR.info(remove_last_period(e))

        # Makes it to trace is correct
        wrapper.__name__ = func.__name__
        return wrapper


    def kill(cls):
        cls.logger.info("Killing Client API.")
        if cls.client_api_state != APIState.LIVE:
            cls.logger.error(f"Cannot kill Client API when not {APIState.LIVE}.")
            return
        cls.http_server.stop()
        cls.client_api_state = APIState.INIT

    @app.route('/peer_connection', methods=['POST'])
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
        cls.logger.info(f"Instructied to connect to peer {peer_id} at {socket_endpoint} with token '{conn_token}'.")

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
