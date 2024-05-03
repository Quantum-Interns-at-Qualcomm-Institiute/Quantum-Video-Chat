from threading import Thread
from flask_socketio import SocketIO, send
from utils.av import generate_flask_namespace
from utils import Endpoint
from functools import total_ordering
from enum import Enum
from utils import ServerError, BadGateway, BadRequest, ParameterError, InvalidParameter, BadAuthentication
from utils import remove_last_period
import logging
from server import Server
from gevent.pywsgi import WSGIServer  # For asynchronous handling
from flask import Flask, jsonify, request
import psutil
import platform
key = 'WiFi 2' if platform.system() == 'Windows' else 'en0'

for prop in psutil.net_if_addrs()[key]:
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


@total_ordering
class SocketState(Enum):
    NEW = 'NEW'
    INIT = 'INIT'
    LIVE = 'LIVE'
    OPEN = 'OPEN'

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented


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

    def HandleExceptions(endpoint_handler):
        """Decorator to handle commonly encountered exceptions in the API"""
        def handler_with_exceptions(*args, **kwargs):
            cls = ServerAPI
            try:
                return endpoint_handler(cls, *args, **kwargs)
            except BadAuthentication as e:
                cls.logger.info(f"Authentication failed for server at {
                                endpoint_handler.__name__}:\n\t{str(e)}")
                return jsonify({"error_code": "403", "error_message": "Forbidden", "details": remove_last_period(e)}), 403
            except BadRequest as e:
                cls.logger.info(str(e))
                return jsonify({"error_code": "400", "error_message": "Bad Request", "details": remove_last_period(e)}), 400
            except ServerError as e:
                cls.logger.error(str(e))
                return jsonify({"error_code": "500", "error_message": "Interal Server Error", "details": remove_last_period(e)}), 500
            except BadGateway as e:
                cls.logger.info(str(e))
                return jsonify({"error_code": "502", "error_message": "Bad Gateway", "details": remove_last_period(e)}), 502
        handler_with_exceptions.__name__ = endpoint_handler.__name__
        return handler_with_exceptions
    # endregion

    @classmethod
    def init(cls, server: Server):
        cls.logger.info(f"Initializing Server API with endpoint {
                        server.api_endpoint}.")
        if cls.state == APIState.LIVE:
            raise ServerError(f"Cannot reconfigure API during server runtime.")
        cls.server = server
        cls.endpoint = server.api_endpoint
        cls.state = APIState.IDLE

    @classmethod
    def start(cls):
        cls.logger.info(f"Starting Server API at {cls.endpoint}.")
        if cls.state == APIState.INIT:
            raise ServerError(f"Cannot start API before initialization.")
        if cls.state == APIState.LIVE:
            raise ServerError(f"Cannot start API: already running.")

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
        Create and store a user with unique `user_id` for authentication. Returns `user_ud`

        Parameters
        ----------
        api_endpoint : tuple
        """

        api_endpoint = get_parameters(request.json, 'api_endpoint')
        cls.logger.info(f"Received request to create a user ID: {api_endpoint}")
        user_id = server.add_user(Endpoint(*api_endpoint))

        return jsonify({'user_id': user_id}), 200

    @app.route('/peer_connection', methods=['POST'])
    @HandleExceptions
    def handle_peer_connection(cls):
        """
        Instruct peer to connect to user's provided socket endpoint

        Request Parameters
        ------------------
        user_id : str
        peer_id : str
        socket_endpoint : tuple(str, int)
        """
        user_id, peer_id = get_parameters(request.json, 'user_id', 'peer_id')
        cls.logger.info(f"Received request from User {
                        user_id} to connect with User {peer_id}.")

        endpoint = cls.server.handle_peer_connection(user_id, peer_id)

        return jsonify({'socket_endpoint': tuple(endpoint)}), 200

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
    def verify_connection(cls, user_id):
        """
        Parameters
        ----------
        user_id : str
        """
        return user_id in cls.users

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
    def init(cls, server, users):
        """
        Parameters
        ----------
        server : Server
        users : tuple, list
            User IDs
        """
        cls.logger.info(f"Initializing WebSocket API with endpoint {
                        server.websocket_endpoint}.")
        if cls.state >= SocketState.LIVE:
            raise ServerError(
                f"Cannot reconfigure WebSocket API during runtime.")

        cls.server = server
        cls.endpoint = server.websocket_endpoint
        cls.state = SocketState.INIT
        for user in users:
            cls.users[user] = None
        cls.instance = cls()
        return cls.instance

    def run(self):
        cls = SocketAPI

        cls.namespaces = generate_flask_namespace(cls)
        ns = sorted(list(cls.namespaces.keys()))
        for name in ns:
            cls.socketio.on_namespace(cls.namespaces[name])

        cls.logger.info(f"Starting WebSocket API.")
        if cls.state == SocketState.NEW:
            raise ServerError(f"Cannot start API before initialization.")
        if cls.state == SocketState.LIVE or cls.state == SocketState.OPEN:
            raise ServerError(f"Cannot start API: already running.")

        # cls.state = SocketState.LIVE # TODO: BE SURE TO UPDATE ON D/C OR SIMILAR
        # cls.socketio.run(cls.app, host=cls.endpoint.ip, port=cls.endpoint.port)

        while True:
            try:
                cls.logger.info(f"Serving WebSocket API at {cls.endpoint}")

                cls.state = SocketState.LIVE
                cls.socketio.run(cls.app, host=cls.endpoint.ip,
                                 port=cls.endpoint.port)
            except OSError as e:
                cls.logger.error(f"Endpoint {cls.endpoint} in use.")

                cls.state = SocketState.INIT
                cls.server.set_websocket_endpoint(
                    Endpoint(cls.endpoint.ip, cls.endpoint.port + 1))
                continue
            cls.logger.info(f"WebSocket API terminated.")
            break

    @classmethod
    def kill(cls):
        cls.logger.info("Killing WebSocket API.")
        if not (cls.state == SocketState.LIVE or cls.state == SocketState.OPEN):
            raise ServerError(f"Cannot kill Socket API when not {
                              SocketState.LIVE} or {SocketState.OPEN}.")
        # "This method must be called from a HTTP or SocketIO handler function."
        cls.socketio.stop()
        cls.state = SocketState.INIT
    # endregion

    # region --- API Endpoints ---

    @socketio.on('connect')  # TODO: Keep track of connection number.
    @HandleExceptions
    def on_connect(cls, user_id):
        cls.logger.info(
            f"Received Socket connection request from User {user_id}.")
        if cls.state != SocketState.LIVE:
            cls.logger.info(f"Cannot accept connection when already {
                            SocketState.OPEN}.")
            # raise UnknownRequester( ... ) # TODO: Maybe different name?
            # or
            # raise ConnectionRefusedError( ... )
            return False
        if not cls.verify_connection(user_id):
            cls.logger.info(f"Socket connection failed authentication.")
            # raise UnknownRequester( ... ) # TODO: Maybe different name?
            # or
            # raise ConnectionRefusedError( ... )
            return False

        cls.logger.info(f"Socket connection from User {user_id} accepted")

        if cls.has_all_users():
            cls.logger.info("Socket API acquired all expected users.")
            cls.state = SocketState.OPEN

    @socketio.on('message')
    @HandleExceptions
    def on_message(cls, user_id, msg):
        cls.logger.info(f"Received message from User {user_id}: '{msg}'")
        send((user_id, msg), broadcast=True)

    @socketio.on('disconnect')
    @HandleExceptions
    def on_disconnect(cls):
        cls.logger.info(f"Client disconnected.")
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
    except KeyboardInterrupt as e:
        logger.info("Intercepted Keyboard Interrupt.")
        ServerAPI.kill()
        logger.info("Exiting main program execution.\n")
        exit()
# endregion
