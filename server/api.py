from flask import Flask, jsonify, request
from gevent.pywsgi import WSGIServer  # For asynchronous handling
from server import Server

#region --- Logging --- # TODO: Add internal logger to API class
import logging
logging.basicConfig(filename='./logs/api.log', level=logging.DEBUG, 
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
#endregion


#region --- Utils ---
from utils import remove_last_period
from utils import ServerError, BadGateway, BadRequest, ParameterError, InvalidParameter, BadAuthentication, UserNotFound

from enum import Enum
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
        if len(args == 0): return get_parameters_from_sequence(data)
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
    if len(validators) == 0: return (*data,)
    if len(data) != len(validators):
        raise ParameterError(f"Expected {len(validators)} parameters but received {len(data)}.")
    
    param_vals = ()
    for i in range(len(data)):
        param_val = data[i]
        validator = validators[i]
        if not validator: validator = lambda x: True

        if not validator(param_val):
            raise InvalidParameter(f"Parameter {i+1} failed validation.")
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
        if type(arg) is tuple: param, validator = arg
        else: param = arg

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
#endregion


#region --- Server API ---
from utils import Endpoint
class ServerAPI: # TODO: Potentially, subclass Thread since server is blocking
    DEFAULT_ENDPOINT = Endpoint('127.0.0.1', 5000)

    app = Flask(__name__)
    http_server = None
    server = None
    endpoint = None
    state = APIState.INIT

    #region --- Utils ---
    logger = logging.getLogger('ServerAPI')

    def HandleAuthentication(endpoint_handler):
        """Decorator to handle commonly encountered exceptions in the API"""
        def handler_with_authentication(cls, *args, **kwargs):
            user_id, sess_token = get_parameters(request.json, 'user_id', 'sess_token')
            if not cls.server.verify_user(user_id, sess_token):
                raise BadAuthentication(f"Authentication failed for user {user_id} with session token '{sess_token}'.")

            return endpoint_handler(cls, *args, **kwargs)
        handler_with_authentication.__name__ = endpoint_handler.__name__
        return handler_with_authentication

    def HandleExceptions(endpoint_handler):
        """Decorator to handle commonly encountered exceptions in the API"""
        def handler_with_exceptions(*args, **kwargs):
            cls = ServerAPI
            try: return endpoint_handler(cls, *args, **kwargs)
            except BadAuthentication as e:
                cls.logger.info(f"Authentication failed for server at {endpoint_handler.__name__}:\n\t{str(e)}")
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
    #endregion


    @classmethod
    def init(cls, server: Server):
        cls.logger.info(f"Initializing Server API with endpoint {server.api_endpoint}.")
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
        
        print(f"Serving Server API on {cls.endpoint}")
        cls.state = APIState.LIVE
        cls.http_server = WSGIServer(tuple(cls.endpoint), cls.app)
        cls.http_server.serve_forever()

    @classmethod
    def kill(cls):
        cls.logger.info("Killing Server API.")
        if cls.state != APIState.LIVE:
            raise ServerError(f"Cannot kill Server API when not {APIState.LIVE}.")
        cls.http_server.stop()
        cls.state = APIState.IDLE


    #region --- API Endpoints ---
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
        Instruct peer to connect to user's provided socket endpoint and self-validate with `conn_token` received from requester.

        Request Parameters
        ------------------
        user_id : str
        peer_id : str
        socket_endpoint : tuple(str, int)
        conn_token : str
        """
        user_id, peer_id, websocket_endpoint, conn_token = get_parameters(request.json, 'user_id', 'peer_id', 'websocket_endpoint', 'conn_token')
        websocket_endpoint = Endpoint(*websocket_endpoint)
        cls.logger.info(f"Received request from User {user_id} to connect with User {peer_id} at {websocket_endpoint}.")
        
        cls.server.handle_peer_connection(user_id, peer_id, websocket_endpoint, conn_token)

        return jsonify({'staus_code': '200'}), 200
        
    #endregion
#endregion


#region --- Main ---
if __name__ == '__main__':
    try:
        server = Server(ServerAPI.DEFAULT_ENDPOINT)
        # server.set_host()
        ServerAPI.init(server)
        ServerAPI.start() # Blocking
    except KeyboardInterrupt as e:
        logger.info("Intercepted Keyboard Interrupt.")
        ServerAPI.kill()
        logger.info("Exiting main program execution.\n")
        exit()
#endregion