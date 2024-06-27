import logging
from datetime import datetime
from enum import Enum
from hashlib import sha256
from json import load as json_load
from threading import Thread
from typing import Tuple

import requests
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit, send
from gevent.pywsgi import WSGIServer  # For asynchronous handling
from namespaces import generate_flask_namespace
from server_exceptions import ServerExceptions
from states import APIState, ServerState, UserState
from user import User, UserManager, UserStorageFactory, UserStorageTypes
from utils import Endpoint, endpoint_in_json, get_parameters, remove_last_period

DEV = True
CONFIG_FILE = f"./{'dev_' if DEV else ''}python_config.json"
LOG_FILE = './server.log'

logging.basicConfig(level=logging.DEBUG if DEV else logging.WARN,
                    format='[%(asctime)s] (%(levelname)s) %(name)s: %(message)s',
                    datefmt='%H:%M:%S',
                    handlers=[
                        logging.FileHandler('./server.log'),
                        logging.StreamHandler() if DEV else None
                    ])

logger = logging.getLogger(__name__)
logger.info(f"-----STARTING NEW LOGGING SESSION AT {datetime.now()}-----")


with open(file=CONFIG_FILE) as json_data:
    config = json_load(json_data)


class VideoChatServerBuilder:
    def __init__(self):
        self.video_chat_server = None
        self.logger = logging.getLogger('VideoChatServerBuilder')
        self.api_endpoint = None
        self.websocket_endpoint = None
        self.socket_api_endpoint = None
        self.user_storage_type = None

    class APIDefault(Enum):
        API_ENDPOINT = Endpoint(ip="localhost", port=9999)
        WEBSOCKET_ENDPOINT = Endpoint(ip="localhost", port=9998)
        SOCKET_API_ENDPOINT = Endpoint(ip="localhost", port=9997)
        STORAGE = UserStorageTypes.DICT

    def set_api_endpoint(self, endpoint: Endpoint = APIDefault.API_ENDPOINT.value):
        """
        Establishes which `Endpoint` object to use for the server's API endpoint

        Keyword Arguments:
            endpoint -- optional `Endpoint` object to override the default value (default: `APIDefault`.ENDPOINT)

        Returns:
            the current instance of the Builder
        """
        self.api_endpoint = Endpoint(*endpoint)  # Makes a copy of the endpoint

        self.logger.info(f"Server's API endpoint will be at {self.api_endpoint}")

        return self

    def set_user_manager(self, user_storage_type: UserStorageTypes = APIDefault.STORAGE.value):
        """
        Establishes the means for which `User`s are stored on the server

        Keyword Arguments:
            user_storage_type -- an optional element of the `UserStorageType` enum to override the default value (default: {APIDefault.STORAGE})

        Returns:
            the current instance of the Builder
        """
        # TODO: can this be a simpler pattern? i.e UserManager(storage=type())... but then where should errors be handled?
        self.user_manager = UserManager(storage=UserStorageFactory().create_storage(user_storage_type))

        self.logger.info(f"Server will use {user_storage_type.name}-based storage to manage users")

        return self

    def set_websocket_endpoint(self, endpoint: Endpoint = APIDefault.WEBSOCKET_ENDPOINT.value):
        """
        Establishes which `Endpoint` object to use for the server's websocket endpoint

        Keyword Arguments:
            endpoint -- optional `Endpoint` object to override the default value  (default: {APIDefault.WEBSOCKET_ENDPOINT})

        Returns:
            the current instance of the Builder
        """
        self.websocket_endpoint = Endpoint(ip=endpoint.ip, port=endpoint.port)  # Makes a copy of the endpoint

        self.logger.info(f"Server's websocket endpoint will be at {self.websocket_endpoint}")

        return self

    def set_socket_api_endpoint(self, endpoint: Endpoint = APIDefault.SOCKET_API_ENDPOINT.value):
        """
        Establishes which `Endpoint` object to use for the server's socket API endpoint

        Keyword Arguments:
            endpoint -- optional `Endpoint` object to override the default value (default: {APIDefault.SOCKET_API_ENDPOINT})

        Returns:
            the current instance of the Builder
        """
        self.socket_api_endpoint = Endpoint(ip=endpoint.ip, port=endpoint.port)  # Makes a copy of the endpoint

        self.logger.info(f"Server's socket API endpoint will be at {self.socket_api_endpoint}")

        return self

    def build(self):
        """
        Creates a new `VideoChatServer` object using the values set by the `set_*(...)` methods

        Raises:
            BaseException: Only raises an exception if API or websocket `Endpoint`s are not set, if `User` Manager has not been established, or if server has already been built

        Returns:
            an instance of `VideoChatServer` configured by the methods called
        """
        if self.video_chat_server is not None:
            logger.error("Cannot re-build server")
            raise BaseException("Cannot re-build server")
        if self.api_endpoint is None:
            logger.error("Must initialize API endpoint before buiding")
            raise BaseException("Must initialize API endpoint before buiding")
        if self.websocket_endpoint is None:
            logger.error("Must initialize websocket endpoint before building")
            raise BaseException("Must initialize websocket endpoint before building")
        if self.socket_api_endpoint is None:
            logger.error("Must initialize socket API endpoint before building")
            raise BaseException("Must initialize socket API endpoint before building")
        if self.user_manager is None:
            logger.error("Must initialize User manager before building")
            raise BaseException("Must initialize User manager before building")
        # TODO: uncomment when we implement QBER properly
        # if self.video_chat_server.qber_manager is None:
        #    logger.error("Must initialize QBER manager before building")
        #    raise BaseException("Must initialize QBER manager before building")

        logger.info("Server values have been properly defined, creating server")
        self.video_chat_server = VideoChatServer(api_endpoint=self.api_endpoint, socket_api_endpoint=self.socket_api_endpoint, websocket_endpoint=self.websocket_endpoint, user_manager=self.user_manager)
        self.video_chat_server.set_server_state(ServerState.INITIALIZED)

        return self.video_chat_server


class VideoChatServer:
    def __init__(self, api_endpoint: Endpoint, websocket_endpoint: Endpoint, socket_api_endpoint: Endpoint, user_manager: UserManager):
        self.logger = logging.getLogger('VideoChatServer')

        self.socket_api_class = SocketAPI  # TODO: Fix, since this is an odd workaround
        self.server_state: ServerState = ServerState.NEW

        self.websocket_endpoint: Endpoint = websocket_endpoint
        self.socket_api_class.endpoint = socket_api_endpoint
        self.api_endpoint: Endpoint = api_endpoint

        self.user_manager: UserManager = user_manager
        # self.qber_manager = None
        self.logger.info("Server setup complete")

    def set_server_state(self, state: ServerState):
        """
        _summary_

        Arguments:
            state -- _description_

        Returns:
            _description_
        """
        if (state < self.server_state):
            return NotImplementedError("State cannot be set to a previous state")  # TODO: Figure out better error class to use here
        self.server_state = state
        self.logger.info(f"Socket's state set to {state}")

    def verify_user(self, user_id: str, sess_token: str):
        """
        _summary_

        Arguments:
            user_id -- _description_
            sess_token -- _description_

        Returns:
            _description_
        """
        try:
            user = self.get_user_by_id(user_id)
            return user.sess_token == sess_token
        except ServerExceptions.USER_NOT_FOUND:
            return False

    def add_user(self, endpoint):
        """
        _summary_

        Arguments:
            endpoint -- _description_

        Raises:
            e: _description_

        Returns:
            _description_
        """
        try:
            user_id, sess_token = self.user_manager.add_user(endpoint)
            self.logger.info(
                f"User {user_id} added with sess_token '{sess_token}'.")
            return user_id, sess_token
        except ServerExceptions.DUPLICATE_USER as e:
            self.logger.error(str(e))
            raise e

    # TODO: Is this method necessary? is this SRP
    def get_user_by_id(self, user_id):
        """
        _summary_

        Arguments:
            user_id -- _description_

        Raises:
            e: _description_

        Returns:
            _description_
        """
        try:
            user_info = self.user_manager.get_user_by_id(user_id)
            self.logger.info(f"Retrieved user with ID {user_id}.")
            return user_info
        except ServerExceptions.USER_NOT_FOUND as e:
            self.logger.error(str(e))
            raise e

    def remove_user(self, user_id):
        """
        _summary_

        Arguments:
            user_id -- _description_

        Raises:
            e: _description_
        """
        try:
            self.user_manager.remove_user(user_id)
            self.logger.info(f"User {user_id} removed successfully.")
        except ServerExceptions.USER_NOT_FOUND as e:
            self.logger.error(str(e))
            raise e

    def set_user_state(self, user_id, state: UserState, peer=None):
        """
        _summary_

        Arguments:
            user_id -- _description_
            state -- _description_

        Keyword Arguments:
            peer -- _description_ (default: {None})

        Raises:
            e: _description_
        """
        try:
            self.user_manager.set_user_state(user_id, state, peer)
            self.logger.info(f"Updated User {user_id} state: {state} ({peer}).")
        except (ServerExceptions.USER_NOT_FOUND, ServerExceptions.INVALID_STATE) as e:
            self.logger.error(str(e))
            raise e

    def contact_client(self, user_id, route, json):
        """
        _summary_

        Arguments:
            user_id -- _description_
            route -- _description_
            json -- _description_

        Raises:
            e: _description_

        Returns:
            _description_
        """
        endpoint = self.get_user_by_id(user_id).api_endpoint(route)
        self.logger.info(f"Contacting Client API for User {user_id} at {endpoint}.")
        try:
            response = requests.post(str(endpoint), json=json)
        except Exception as e:
            self.logger.error(f"Unable to reach Client API for User {user_id} at endpoint {endpoint}.")
            # TODO: Figure out specifically what exception is raised so I can catch only that,
            # and then handle it instead of re-raising
            # (or maybe re-raise different exception and then caller can handle)
            raise e
        return response

    def start_websocket(self, users: Tuple[User, User]):
        """
        _summary_

        Arguments:
            users -- _description_

        Raises:
            ServerExceptions.SERVER_ERROR: _description_
        """
        self.logger.info("Starting WebSocket API.")
        if not self.websocket_endpoint:
            raise ServerExceptions.SERVER_ERROR(
                "Cannot start WebSocket API without defined endpoint.")

        self.websocket_instance = self.socket_api_class.init(self, users)
        self.websocket_instance.start()

    def handle_peer_connection(self, user_id: str, peer_id: str):
        """
        _summary_

        Arguments:
            user_id -- _description_
            peer_id -- _description_

        Raises:
            ServerExceptions.BAD_REQUEST: _description_
            ServerExceptions.BAD_REQUEST: _description_
            ServerExceptions.BAD_REQUEST: _description_
            ServerExceptions.INVALID_STATE: _description_
            ServerExceptions.INVALID_STATE: _description_
            ServerExceptions.BAD_GATEWAY: _description_
            ServerExceptions.BAD_GATEWAY: _description_

        Returns:
            _description_
        """
        if user_id == peer_id:
            raise ServerExceptions.BAD_REQUEST(f"Cannot intermediate connection between User {user_id} and self.")

        # TODO: Validate state(s)
        # if peer is not IDLE, reject
        try:
            requester = self.get_user_by_id(user_id)
        except ServerExceptions.USER_NOT_FOUND:
            raise ServerExceptions.BAD_REQUEST(f"User {user_id} does not exist.")
        try:
            host = self.get_user_by_id(peer_id)
        except ServerExceptions.USER_NOT_FOUND:
            raise ServerExceptions.BAD_REQUEST(f"User {peer_id} does not exist.")

        if host.state != UserState.IDLE:
            raise ServerExceptions.INVALID_STATE(f"Cannot connect to peer User {peer_id}: peer must be IDLE.")
        if requester.state != UserState.IDLE:
            raise ServerExceptions.INVALID_STATE(f"Cannot connect User {user_id} to peer: User must be IDLE.")

        self.logger.info(f"Contacting User {peer_id} to connect to User {user_id}.")

        self.start_websocket(users=(requester, host))

        try:
            response = self.contact_client(peer_id, '/peer_connection', json={
                'sess_token': host.sess_token,
                'peer_id': requester.id,
                'socket_endpoint': tuple(self.websocket_endpoint),
                'conn_token': self.socket_api_class.conn_token
            })
        except Exception:
            raise ServerExceptions.BAD_GATEWAY(f"Unable to reach peer User {peer_id}.")
        self.logger.info(f"Status code: {response.status_code}")
        if response.status_code != 200:
            f"Peer User {peer_id} refused connection request."
            raise ServerExceptions.BAD_GATEWAY(
                f"Peer User {peer_id} refused connection request.")
        self.logger.info(f"Peer User {peer_id} accepted connection request.")
        return self.websocket_endpoint, self.socket_api_class.conn_token


class SocketAPI(Thread):
    DEFAULT_ENDPOINT = Endpoint(ip=config["SERVER_SOCKET_API"]["ADDRESS"], port=config["SERVER_SOCKET_API"]["PORT"])  # TODO: Read from config, maybe?

    app = Flask(__name__)
    socketio = SocketIO(app)
    instance = None  # Make sure this guy gets cleared if the API d/cs or similar
    server = None
    endpoint = None
    state = ServerState.NEW
    namespaces = None

    conn_token = None
    users = {}

    logger = logging.getLogger('SocketAPI')  # TODO: Magic string is gross

    @classmethod
    def has_all_users(cls):
        for user in cls.users:
            if not cls.users[user]:
                return False
        return True

    @classmethod
    def generate_conn_token(cls, users: Tuple[User, User]):
        return sha256(bytes(a ^ b for a, b in zip(users[0].id.encode(), users[1].id.encode()))).hexdigest()

    @classmethod
    def generate_sess_token(cls, user_id):
        return sha256(user_id.encode()).hexdigest()

    @classmethod
    def verify_conn_token(cls, conn_token):
        return conn_token == cls.conn_token

    @classmethod
    def verify_sess_token(cls, user_id, sess_token):
        if user_id not in cls.users:
            raise ServerExceptions.USER_NOT_FOUND(f"User {user_id} not found.")
        return sess_token == cls.users[user_id]

    @classmethod
    def verify_connection(cls, auth):
        """
        Parameters
        ----------
        auth : tuple
            (user_id, conn_token)
        """
        user_id, conn_token = auth
        if user_id not in cls.users:
            return False
        if conn_token != cls.conn_token:
            return False
        return True

    def HandleAuthentication(endpoint_handler):
        """
        Decorator to handle authentication for existing users.
        Pass `cls` and `user_id` to handler function.

        NOTE: Assumes `cls` has been passed by @HandleExceptions
        NOTE: This should never be called explicitly

        Parameters
        ----------
        auth : (user_id, sess_token)
            user_id : str,
            sess_token : str
        """
        def handler_with_authentication(cls, auth, *args, **kwargs):
            user_id, sess_token = get_parameters(auth)
            try:
                if not cls.verify_sess_token(user_id, sess_token):
                    raise ServerExceptions.BAD_AUTHENTICATION(f"Authentication failed for User {user_id} with token '{sess_token}'.")
            except ServerExceptions.USER_NOT_FOUND as e:
                raise ServerExceptions.BAD_AUTHENTICATION(f"Authentication failed for User {user_id} with token '{sess_token}': {str(e)}.")

            endpoint_handler(cls, user_id)
        return handler_with_authentication

    def HandleExceptions(endpoint_handler):
        """
        Decorator to handle commonly encountered exceptions.

        NOTE: This should never be called explicitly.
        """
        def handler_with_exceptions(*args, **kwargs):
            cls = SocketAPI
            return endpoint_handler(cls, *args, **kwargs)
            # try: return endpoint_handler(cls, *args, **kwargs)
            # except UnknownRequester as e:
            #     cls.logger.error(f"Unknown requester at {endpoint_handler.__name__}:\n\t{str(e)}")
            #     return jsonify({"error_code": "403", "error_message": "Forbidden", "details": str(e)}), 403
            # except ParameterError as e:
            #     cls.logger.error(str(e))
            #     return jsonify({"error_code": "400", "error_message": "Bad Request", "details": str(e)}), 400
        return handler_with_exceptions

    @classmethod
    def init(cls, server, users: Tuple[User, User]):
        """
        Parameters
        ----------
        server : VideoChatServer
        users : tuple (requester_id, host_id)
        """
        cls.logger.info(f"Initializing WebSocket API with endpoint {server.websocket_endpoint}.")
        if cls.state >= ServerState.LIVE:
            raise ServerExceptions.SERVER_ERROR(
                "Cannot reconfigure WebSocket API during runtime.")

        cls.video_chat_server = server
        cls.endpoint = server.websocket_endpoint
        cls.conn_token = cls.generate_conn_token(users)
        cls.state = ServerState.INIT
        for user in users:
            cls.users[user.id] = User(*user)
        cls.instance = cls()
        return cls.instance

    def run(self):
        cls = SocketAPI

        cls.namespaces = generate_flask_namespace(cls)
        ns = sorted(list(cls.namespaces.keys()))
        for name in ns:
            cls.socketio.on_namespace(cls.namespaces[name])

        cls.logger.info("Starting WebSocket API.")
        if cls.state == ServerState.NEW:
            raise ServerExceptions.SERVER_ERROR("Cannot start API before initialization.")
        if cls.state == ServerState.LIVE or cls.state == ServerState.OPEN:
            raise ServerExceptions.SERVER_ERROR("Cannot start API: already running.")

        # cls.state = ServerState.LIVE # TODO: BE SURE TO UPDATE ON D/C OR SIMILAR
        # cls.socketio.run(cls.app, host=cls.endpoint.ip, port=cls.endpoint.port)

        while True:
            try:
                cls.logger.info(f"Serving WebSocket API at {cls.endpoint}")

                cls.state = ServerState.LIVE
                cls.socketio.run(cls.app, host=cls.endpoint.ip,
                                 port=cls.endpoint.port)
            except OSError:
                cls.logger.error(f"Endpoint {cls.endpoint} in use.")

                cls.state = ServerState.INIT
                cls.video_chat_server.set_websocket_endpoint(
                    Endpoint(cls.endpoint.ip, cls.endpoint.port + 1))
                continue
            cls.logger.info("WebSocket API terminated.")
            break

    @classmethod
    def kill(cls):
        cls.logger.info("Killing WebSocket API.")
        if not (cls.state == ServerState.LIVE or cls.state == ServerState.OPEN):
            raise ServerExceptions.SERVER_ERROR(f"Cannot kill Socket API when not {ServerState.LIVE} or {ServerState.OPEN}.")
        # "This method must be called from a HTTP or SocketIO handler function."
        cls.socketio.stop()
        cls.state = ServerState.INIT

    @socketio.on('connect')  # TODO: Keep track of connection number.
    @HandleExceptions
    def on_connect(cls, auth):
        user_id, conn_token = auth
        cls.logger.info(f"Received Socket connection request from User {user_id} with connection token '{conn_token}'.")
        if cls.state != ServerState.LIVE:
            cls.logger.info(f"Cannot accept connection when already {ServerState.OPEN}.")
            # raise UnknownRequester( ... ) # TODO: Maybe different name?
            # or
            # raise ConnectionRefusedError( ... )
            return False
        if not cls.verify_connection(auth):
            cls.logger.info("Socket connection failed authentication.")
            # raise UnknownRequester( ... ) # TODO: Maybe different name?
            # or
            # raise ConnectionRefusedError( ... )
            return False

        sess_token = cls.generate_sess_token(user_id)
        cls.users[user_id] = sess_token
        cls.logger.info(f"Socket connection from User {user_id} accepted; yielding session token '{sess_token}'")
        emit('token', sess_token)

        # TODO: What is this block?
        # if cls.has_all_users():
        #     cls.logger.info("Socket API acquired all expected users.")
        #     cls.state = ServerState.OPEN

    @socketio.on('message')
    @HandleExceptions
    def on_message(cls, auth, msg):
        user_id, sess_token = auth
        user_id = user_id
        cls.logger.info(f"Received message from User {user_id}: '{msg}'")
        if not cls.verify_sess_token(*auth):
            cls.logger.info(f"Authentication failed for User {user_id} with token '{sess_token}' at on_message.")
            return

        send((user_id, msg), broadcast=True)

    @socketio.on('disconnect')
    @HandleExceptions
    def on_disconnect(cls):
        cls.logger.info("Client disconnected.")
        # Broadcast to all clients to disconnect
        # Close all connections (if that's a thing)
        # Kill Web Socket
        # State returns to INIT


class ServerAPI:  # TODO: Potentially, subclass Thread since server is blocking
    logger = logging.getLogger('ServerAPI')
    server_api_state = APIState.INIT

    video_chat_server = None

    app = Flask(__name__)
    server = None

    endpoint = None
    http_server = None

    @classmethod
    def init(cls, server: VideoChatServer):
        """
        _summary_

        Arguments:
            server -- _description_

        Raises:
            ServerExceptions.SERVER_ERROR: _description_
        """
        cls.logger.info("Attempting to initialize Server API...")
        if cls.server_api_state == APIState.LIVE:
            raise ServerExceptions.SERVER_ERROR("Cannot reconfigure API during server runtime.")
        cls.video_chat_server = server
        cls.endpoint = server.api_endpoint
        cls.server_api_state = APIState.IDLE

    @classmethod
    def start(cls):
        """
        _summary_

        Raises:
            ServerExceptions.SERVER_ERROR: _description_
            ServerExceptions.SERVER_ERROR: _description_
        """
        cls.logger.info("Starting Server API...")
        if cls.server_api_state == APIState.INIT:
            raise ServerExceptions.SERVER_ERROR("Cannot start API before initialization.")
        if cls.server_api_state == APIState.LIVE:
            raise ServerExceptions.SERVER_ERROR("Cannot start API: already running.")

        cls.logger.info(f"Now serving Server API on {cls.endpoint}")
        cls.server_api_state = APIState.LIVE
        cls.http_server = WSGIServer(tuple(cls.endpoint), cls.app)
        cls.http_server.serve_forever()

    def HandleAuthentication(func: callable):
        """
        _summary_

        Arguments:
            func -- _description_

        Raises:
            ServerExceptions.BAD_AUTHENTICATION: _description_

        Returns:
            _description_
        """
        """Decorator to handle commonly encountered exceptions in the API"""
        def wrapper(cls, *args, **kwargs):
            user_id, sess_token = get_parameters(
                request.json, 'user_id', 'sess_token')
            if not cls.video_chat_server.verify_user(user_id, sess_token):
                raise ServerExceptions.BAD_AUTHENTICATION(f"Authentication failed for user {user_id} with session token '{sess_token}'.")

            return func(cls, *args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper

    def HandleExceptions(endpoint_handler):
        """
        _summary_

        Arguments:
            endpoint_handler -- _description_

        Returns:
            _description_
        """
        """Decorator to handle commonly encountered exceptions in the API"""
        def handler_with_exceptions(*args, **kwargs):
            cls = ServerAPI
            try:
                return endpoint_handler(cls, *args, **kwargs)
            except ServerExceptions.BAD_AUTHENTICATION as e:
                cls.logger.info(f"Authentication failed for server at {endpoint_handler.__name__}:\n\t{str(e)}")
                return jsonify({"error_code": "403",
                                "error_message": "Forbidden",
                                "details": remove_last_period(e)}),
                403
            except ServerExceptions.BAD_REQUEST as e:
                cls.logger.info(str(e))
                return jsonify({"error_code": "400",
                                "error_message": "Bad Request",
                                "details": remove_last_period(e)}),
                400
            except ServerExceptions.SERVER_ERROR as e:
                cls.logger.error(str(e))
                return jsonify({"error_code": "500",
                                "error_message": "Interal Server Error",
                                "details": remove_last_period(e)}), 500
            except ServerExceptions.BAD_GATEWAY as e:
                cls.logger.info(str(e))
                return jsonify({"error_code": "502",
                                "error_message": "Bad Gateway",
                                "details": remove_last_period(e)}),
                502
        handler_with_exceptions.__name__ = endpoint_handler.__name__
        return handler_with_exceptions

    @classmethod
    def kill(cls):
        """
        _summary_

        Raises:
            ServerExceptions.SERVER_ERROR: _description_
        """
        cls.logger.info("Killing Server API.")
        if cls.server_api_state != APIState.LIVE:
            raise ServerExceptions.SERVER_ERROR(
                f"Cannot kill Server API when not {APIState.LIVE}.")
        cls.http_server.stop()
        cls.server_api_state = APIState.IDLE

    @app.route('/create_user', methods=['POST'])
    @HandleExceptions
    def create_user(cls):
        """
        _summary_

        Returns:
            _description_
        """
        """
        Create and store a user with unique `user_id` and `sess_token` for authentication. Return both.

        Parameters
        ----------
        api_endpoint : tuple
        """
        cls.logger.info("Received request to create a user ID.")

        api_endpoint, = get_parameters(request.json, 'api_endpoint')
        cls.logger.info(api_endpoint)
        user_id, sess_token = cls.video_chat_server.add_user(Endpoint(*api_endpoint))

        return jsonify({'sess_token': sess_token, 'user_id': user_id}), 200

    # TODO: Re-implement method below
    # @app.route('/remove_user', methods=['DELETE'])
    # def remove_user(cls):
    #     user_id, token = get_parameters(request.json, )
    #     cls.logger.info("Received request to remove a user ID.")
    #     if not server.verify_identity(user_id,token):
    #         return jsonify({"error_code": "403", "error_message": "Forbidden", "details": "Identity Mismatch"}), 403

    #     try:
    #         server.remove_user(user_id)
    #         return jsonify({"error": "Not Implemented"}), 501
    #     except Exception as e:
    #         cls.logger.error(f"An error occurred while removing user ID: {e}")
    #         return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500

    @app.route('/peer_connection', methods=['POST'])
    @HandleExceptions
    @HandleAuthentication
    def handle_peer_connection(cls):
        """
        Instruct peer to connect to user's provided socket endpoint and self-validate
        with `conn_token` received from requester.

        Request Parameters
        ------------------
        user_id : str
        peer_id : str
        socket_endpoint : tuple(str, int)
        conn_token : str
        """
        user_id, peer_id = get_parameters(request.json, 'user_id', 'peer_id')
        cls.logger.info(f"Received request from User {user_id} to connect with User {peer_id}.")

        endpoint, conn_token = cls.video_chat_server.handle_peer_connection(
            user_id, peer_id)

        return jsonify({'socket_endpoint': tuple(endpoint), 'conn_token': conn_token}), 200


if __name__ == '__main__':
    try:
        builder = VideoChatServerBuilder()

        # TODO: Is this the best way to do this? I could move defaults out of functional parameters and pass in the config file, maybe even to the builder? Most of this code is not meant to be seen so re-usabilty need is low
        if endpoint_in_json(json=config, key="SERVER_API"):
            builder.set_api_endpoint(endpoint=Endpoint(ip=config["SERVER_API"]["ADDRESS"], port=config["SERVER_API"]["PORT"]))
        else:
            logger.warning("Server API's ADDRESS or PORT not specified in config, using default values")
            builder.set_api_endpoint()

        if endpoint_in_json(json=config, key="SERVER_WEBSOCKET"):
            builder.set_websocket_endpoint(endpoint=Endpoint(ip=config["SERVER_WEBSOCKET"]["ADDRESS"], port=config["SERVER_WEBSOCKET"]["PORT"]))
        else:
            logger.warning("Server Websocket's ADDRESS or PORT not specified in config, using default values")
            builder.set_websocket_endpoint()

        if endpoint_in_json(json=config, key="SERVER_SOCKET_API"):
            builder.set_socket_api_endpoint(endpoint=Endpoint(ip=config["SERVER_SOCKET_API"]["ADDRESS"], port=config["SERVER_SOCKET_API"]["PORT"]))
        else:
            logger.warning("Server socket API's ADDRESS or PORT not specified in config, using default values")
            builder.set_socket_api_endpoint()

        # TODO: fix
        if "USER_STORAGE_TYPE" in config and config["USER_STORAGE_TYPE"] in UserStorageTypes:
            builder.set_user_manager(user_storage_type=config["USER_STORAGE_TYPE"])
        else:
            logger.warning("Server's User storage type not specified, or an invalid type has been specified. Using default value")
            builder.set_user_manager()

        server = builder.build()

        ServerAPI.init(server=server)
        ServerAPI.start()  # Blocking
    except KeyboardInterrupt:
        ServerAPI.kill()
        logger.info("Intercepted Keyboard Interrupt.")
        logger.info("Exiting main program execution.\n")
        exit()
