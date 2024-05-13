from threading import Thread
import hashlib
from typing import Tuple
from flask_socketio import SocketIO, send, emit

from utils.namespaces.av_controller import generate_flask_namespace
from user import User
from utils import Endpoint
from enum import Enum
from utils import ServerError, BadGateway, BadRequest, ParameterError, InvalidParameter, BadAuthentication, UserNotFound
from utils import remove_last_period
import logging
from server import Server, SocketState
from gevent.pywsgi import WSGIServer  # For asynchronous handling
from flask import Flask, jsonify, request
import psutil
import platform

AD_HOC = True
search_string = ('Ethernet 2', 'en7') if AD_HOC else ('Wi-Fi', 'en0')
for prop in psutil.net_if_addrs()[search_string[0 if platform.system() == 'Windows' else 1]]:
    if prop.family == 2:
        ip = prop.address


# region --- Logging --- # TODO: Add internal logger to API class
logging.basicConfig(filename='./logs/api.log', level=logging.DEBUG,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
# endregion


# region --- Utils ---


class APIState(Enum):
    INIT = 'INIT'
    IDLE = 'IDLE'
    LIVE = 'LIVE'


def get_parameters(data, *args):
    """
    Returns desired parameters from a collection with optional data validation.
    Validator functions return true iff associated data is valid.

    Parameters
    ----------
    data : list, tuple, dict
    arg : list, optional
        If `data` is a sequence, list of validator functions (or `None`).
    arg : str, optional
        If `data` is a dict, key of desired data.
    arg : 2-tuple, optional
        If `data` is a dict:
        arg[0] : str,
        arg[1] : func
    """
    if isinstance(data, list) or isinstance(data, tuple):
        if len(args == 0):
            return get_parameters_from_sequence(data)
        return get_parameters_from_sequence(data, args[0])
    if isinstance(data, dict):
        return get_parameters_from_dict(data, *args)
    raise NotImplementedError


def get_parameters_from_sequence(data, validators=[]):
    """
    Returns desired data from a list or or tuple with optional data validation.
    Validator functions return true iff associated data is valid.

    Parameters
    ----------
    data : list, tuple
    validators : list, tuple, optional
        Contains validator functions (or `None`) which return true iff associated data is acceptable.
        Must match order and length of `data`.
    """
    if len(validators) == 0:
        return (*data,)
    if len(data) != len(validators):
        raise ParameterError(
            f"Expected {len(validators)} parameters but received {len(data)}.")

    param_vals = ()
    for i in range(len(data)):
        param_val = data[i]
        validator = validators[i]
        if not validator:
            validator = lambda x: True

        if not validator(param_val):
            raise InvalidParameter(f"Parameter {i + 1} failed validation.")
        param_vals += (*param_vals, param_val)
    return param_vals


def get_parameters_from_dict(data, *args):
    """
    Returns desired data from a dict with optional data validation.
    Validator functions return true iff associated data is valid.

    Parameters
    ----------
    data : dict
    arg : str, optional
        Key of desired data
    arg : 2-tuple, optional
        arg[0] : str,
        arg[1] : func
    """
    param_vals = ()
    for i in range(len(args)):
        arg = args[i]
        validator = lambda x: True
        if type(arg) is tuple:
            param, validator = arg
        else:
            param = arg

        if param in data:
            param_val = data.get(param)
        else:
            raise ParameterError(f"Expected parameter '{param}' not received.")

        if not validator(param_val):
            raise InvalidParameter(f"Parameter '{param}' failed validation.")

        param_vals = (*param_vals, param_val)
    return param_vals


def is_type(type_):
    return lambda x: isinstance(x, type_)
# endregion


# region --- Server API ---


class ServerAPI:  # TODO: Potentially, subclass Thread since server is blocking
    DEFAULT_ENDPOINT = Endpoint(ip, 5000)

    app = Flask(__name__)
    http_server = None
    server = None
    endpoint = None
    state = APIState.INIT

    # region --- Utils ---
    logger = logging.getLogger('ServerAPI')

    def HandleAuthentication(func: callable):
        """Decorator to handle commonly encountered exceptions in the API"""
        def wrapper(cls, *args, **kwargs):
            user_id, sess_token = get_parameters(
                request.json, 'user_id', 'sess_token')
            if not cls.server.verify_user(user_id, sess_token):
                raise BadAuthentication(f"Authentication failed for user {user_id} with session token '{sess_token}'.")

            return func(cls, *args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper

    def HandleExceptions(endpoint_handler):
        """Decorator to handle commonly encountered exceptions in the API"""
        def handler_with_exceptions(*args, **kwargs):
            cls = ServerAPI
            try:
                return endpoint_handler(cls, *args, **kwargs)
            except BadAuthentication as e:
                cls.logger.info(f"Authentication failed for server at {endpoint_handler.__name__}:\n\t{str(e)}")
                return jsonify({"error_code": "403",
                                "error_message": "Forbidden",
                                "details": remove_last_period(e)}),
                403
            except BadRequest as e:
                cls.logger.info(str(e))
                return jsonify({"error_code": "400",
                                "error_message": "Bad Request",
                                "details": remove_last_period(e)}),
                400
            except ServerError as e:
                cls.logger.error(str(e))
                return jsonify({"error_code": "500",
                                "error_message": "Interal Server Error",
                                "details": remove_last_period(e)}), 500
            except BadGateway as e:
                cls.logger.info(str(e))
                return jsonify({"error_code": "502",
                                "error_message": "Bad Gateway",
                                "details": remove_last_period(e)}),
                502
        handler_with_exceptions.__name__ = endpoint_handler.__name__
        return handler_with_exceptions
    # endregion

    @classmethod
    def init(cls, server: Server):
        cls.logger.info(f"Initializing Server API with endpoint {server.api_endpoint}.")
        if cls.state == APIState.LIVE:
            raise ServerError("Cannot reconfigure API during server runtime.")
        cls.server = server
        cls.endpoint = server.api_endpoint
        cls.state = APIState.IDLE

    @classmethod
    def start(cls):
        cls.logger.info(f"Starting Server API at {cls.endpoint}.")
        if cls.state == APIState.INIT:
            raise ServerError("Cannot start API before initialization.")
        if cls.state == APIState.LIVE:
            raise ServerError("Cannot start API: already running.")

        print(f"Serving Server API on {cls.endpoint}")
        cls.state = APIState.LIVE
        cls.http_server = WSGIServer(tuple(cls.endpoint), cls.app)
        cls.http_server.serve_forever()

    @classmethod
    def kill(cls):
        cls.logger.info("Killing Server API.")
        if cls.state != APIState.LIVE:
            raise ServerError(
                f"Cannot kill Server API when not {APIState.LIVE}.")
        cls.http_server.stop()
        cls.state = APIState.IDLE

    # region --- API Endpoints ---

    @app.route('/create_user', methods=['POST'])
    @HandleExceptions
    def create_user(cls):
        """
        Create and store a user with unique `user_id` and `sess_token` for authentication. Return both.

        Parameters
        ----------
        api_endpoint : tuple
        """
        cls.logger.info("Received request to create a user ID.")

        api_endpoint, = get_parameters(request.json, 'api_endpoint')
        print(api_endpoint)
        user_id, sess_token = server.add_user(Endpoint(*api_endpoint))

        return jsonify({'sess_token': sess_token, 'user_id': user_id}), 200

    # @app.route('/remove_user', methods=['DELETE'])
    # async def remove_user(user_id, token):
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

        endpoint, conn_token = cls.server.handle_peer_connection(
            user_id, peer_id)

        return jsonify({'socket_endpoint': tuple(endpoint), 'conn_token': conn_token}), 200

    # endregion
# endregion


# region --- Socket API ---


class SocketAPI(Thread):
    DEFAULT_ENDPOINT = Endpoint(ip, 3000)  # TODO: Read from config, maybe?

    app = Flask(__name__)
    socketio = SocketIO(app)
    instance = None  # Make sure this guy gets cleared if the API d/cs or similar
    server = None
    endpoint = None
    state = SocketState.NEW
    namespaces = None

    conn_token = None
    users = {}

    # region --- Utils ---
    logger = logging.getLogger('SocketAPI')  # TODO: Magic string is gross

    @classmethod
    def has_all_users(cls):
        for user in cls.users:
            if not cls.users[user]:
                return False
        return True

    @classmethod
    def generate_conn_token(cls, users: Tuple[User, User]):
        return hashlib.sha256(bytes(a ^ b for a, b in zip(users[0].id.encode(), users[1].id.encode()))).hexdigest()

    @classmethod
    def generate_sess_token(cls, user_id):
        return hashlib.sha256(user_id.encode()).hexdigest()

    @classmethod
    def verify_conn_token(cls, conn_token):
        return conn_token == cls.conn_token

    @classmethod
    def verify_sess_token(cls, user_id, sess_token):
        if user_id not in cls.users:
            raise UserNotFound(f"User {user_id} not found.")
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
                    raise BadAuthentication(f"Authentication failed for User {user_id} with token '{sess_token}'.")
            except UserNotFound as e:
                raise BadAuthentication(f"Authentication failed for User {user_id} with token '{sess_token}': {str(e)}.")

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
    # endregion

    # region --- External 'Instance' Interface ---

    @classmethod
    def init(cls, server, users: Tuple[User, User]):
        """
        Parameters
        ----------
        server : Server
        users : tuple (requester_id, host_id)
        """
        cls.logger.info(f"Initializing WebSocket API with endpoint {server.websocket_endpoint}.")
        if cls.state >= SocketState.LIVE:
            raise ServerError(
                "Cannot reconfigure WebSocket API during runtime.")

        cls.server = server
        cls.endpoint = server.websocket_endpoint
        cls.conn_token = cls.generate_conn_token(users)
        cls.state = SocketState.INIT
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
        if cls.state == SocketState.NEW:
            raise ServerError("Cannot start API before initialization.")
        if cls.state == SocketState.LIVE or cls.state == SocketState.OPEN:
            raise ServerError("Cannot start API: already running.")

        # cls.state = SocketState.LIVE # TODO: BE SURE TO UPDATE ON D/C OR SIMILAR
        # cls.socketio.run(cls.app, host=cls.endpoint.ip, port=cls.endpoint.port)

        while True:
            try:
                print(f"Serving WebSocket API at {cls.endpoint}")
                cls.logger.info(f"Serving WebSocket API at {cls.endpoint}")

                cls.state = SocketState.LIVE
                cls.socketio.run(cls.app, host=cls.endpoint.ip,
                                 port=cls.endpoint.port)
            except OSError:
                print(f"Listener endpoint {cls.endpoint} in use.")
                cls.logger.error(f"Endpoint {cls.endpoint} in use.")

                cls.state = SocketState.INIT
                cls.server.set_websocket_endpoint(
                    Endpoint(cls.endpoint.ip, cls.endpoint.port + 1))
                continue
            cls.logger.info("WebSocket API terminated.")
            break

    @classmethod
    def kill(cls):
        cls.logger.info("Killing WebSocket API.")
        if not (cls.state == SocketState.LIVE or cls.state == SocketState.OPEN):
            raise ServerError(f"Cannot kill Socket API when not {SocketState.LIVE} or {SocketState.OPEN}.")
        # "This method must be called from a HTTP or SocketIO handler function."
        cls.socketio.stop()
        cls.state = SocketState.INIT
    # endregion

    # region --- API Endpoints ---

    @socketio.on('connect')  # TODO: Keep track of connection number.
    @HandleExceptions
    def on_connect(cls, auth):
        user_id, conn_token = auth
        cls.logger.info(f"Received Socket connection request from User {user_id} with connection token '{conn_token}'.")
        if cls.state != SocketState.LIVE:
            cls.logger.info(f"Cannot accept connection when already {SocketState.OPEN}.")
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
        #     cls.state = SocketState.OPEN

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

    # endregion
# endregion


# region --- Main ---
if __name__ == '__main__':
    try:
        server = Server(ServerAPI.DEFAULT_ENDPOINT, SocketAPI, SocketState)
        # server.set_host()
        ServerAPI.init(server)
        ServerAPI.start()  # Blocking
    except KeyboardInterrupt:
        logger.info("Intercepted Keyboard Interrupt.")
        ServerAPI.kill()
        logger.info("Exiting main program execution.\n")
        exit()
# endregion
