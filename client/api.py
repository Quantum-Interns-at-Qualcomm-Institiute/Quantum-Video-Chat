from flask import Flask, jsonify, request
from flask_socketio import SocketIO, send, emit
from flask_socketio import ConnectionRefusedError
from threading import Thread
# TODO: Look into usage for gevent
from gevent.pywsgi import WSGIServer # For asynchronous handling

#region --- Logging ---
import logging
logging.basicConfig(filename='./logs/api.log', level=logging.DEBUG, 
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
#endregion


#region --- Utils ---
from utils import ClientState
from utils import Endpoint
from utils import get_parameters, is_type, remove_last_period
from utils import ServerError, BadGateway, BadRequest, ParameterError, InvalidParameter, BadAuthentication, UserNotFound

from enum import Enum
from functools import total_ordering
@total_ordering
class APIState(Enum): #TODO: Make an ordered enum interface kek-dubbers
    NEW = 'NEW'
    INIT = 'INIT'
    LIVE = 'LIVE'

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented
    
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
#endregion


#region --- Client API ---
class ClientAPI(Thread):
    DEFAULT_ENDPOINT = Endpoint('127.0.0.1',4000) # TODO: Read from config, maybe?

    app = Flask(__name__)
    http_server = None
    client = None
    endpoint = None
    state = APIState.NEW

    # SO FUCKING HACKY AAAH KILL MYLSEF
    instance = None # Make sure this guy gets cleared if the API d/cs or similar

    #region --- Utils ---
    logger = logging.getLogger('ClientAPI') # TODO: Magic string is gross

    @classmethod
    def verify_server(cls, sess_token):
        if type(sess_token) is str:
            return True
        raise BadAuthentication(f"Unrecognized session token '{sess_token}' from server.")


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
                raise BadAuthentication(f"Authentication failed for server with token '{sess_token}'.")

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


    #region --- External 'Instance' Interface ---
    @classmethod
    def init(cls, client):
        cls.logger.info(f"Initializing Client API with endpoint {client.api_endpoint}.")
        if cls.state == APIState.LIVE:
            raise ServerError(f"Cannot reconfigure API during server runtime.")
        
        cls.client = client
        cls.endpoint = client.api_endpoint
        cls.state = APIState.INIT
        cls.instance = cls()
        return cls.instance

    def run(self):
        cls = self.__class__

        cls.logger.info(f"Starting Client API.")
        if cls.state == APIState.NEW:
            raise ServerError(f"Cannot start API before initialization.")
        if cls.state == APIState.LIVE:
            raise ServerError(f"Cannot start API: already running.")
        
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
                cls.client.set_api_endpoint(Endpoint(cls.endpoint.ip, cls.endpoint.port + 1))
                continue
            cls.logger.info(f"Client API terminated.")
            break


    @classmethod
    def kill(cls):
        cls.logger.info("Killing Client API.")
        if cls.state != APIState.LIVE:
            cls.logger.error(f"Cannot kill Client API when not {APIState.LIVE}.")
            return
        cls.http_server.stop()
        cls.state = APIState.INIT
    #endregion
    

    #region --- API Endpoints ---
    @app.route('/peer_connection', methods=['POST'])
    @HandleExceptions
    @HandleAuthentication
    def handle_peer_connection(cls):
        """
        Receive incoming peer connection request.
        Poll client user. Instruct client to attempt socket connection to specified peer and self-identify with provided connection token.

        Request Parameters
        ------------------
        peer_id : str
        socket_endpoint : tuple
        conn_token : string
        """
        peer_id, socket_endpoint, conn_token = get_parameters(request.json, 'peer_id', 'socket_endpoint', 'conn_token')
        socket_endpoint = Endpoint(*socket_endpoint)
        cls.logger.info(f"Received instruction to connect to peer {peer_id} at {socket_endpoint} with token '{conn_token}'.")
        
        try:
            res = cls.client.handle_peer_connection(peer_id, socket_endpoint, conn_token)
        except Exception:
            # TODO: Why did the connection fail?
            cls.logger.info(f"Responding with 500")
            return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": "Connectioned failed"}), 500
        
        cls.logger.info("client.handle_peer_connection() finished.")
        if not res:
            # User Refused
            logger.info(f"Responding with 418")
            return jsonify({"error_code": "418", "error_message": "I'm a teapot", "details": "Peer User refused connection"}), 418
        # TODO: What should we return?
        cls.logger.info(f"Responding with 200")
        return jsonify({'status_code': '200'}), 200
    #endregion
#endregion


#region --- Socket API ---
class SocketAPI(Thread):
    DEFAULT_ENDPOINT = Endpoint('127.0.0.1',3000) # TODO: Read from config, maybe?

    app = Flask(__name__)
    socketio = SocketIO(app)
    instance = None # Make sure this guy gets cleared if the API d/cs or similar
    client = None
    endpoint = None
    state = SocketState.NEW

    conn_token = None
    users = {}

    #region --- Utils ---
    logger = logging.getLogger('SocketAPI') # TODO: Magic string is gross

    @classmethod
    def has_all_users(cls):
        for user in cls.users:
            if not cls.users[user]: return False
        return True

    @classmethod
    def generate_conn_token(cls):
        return 'abcdefghijklmnop'

    @classmethod
    def generate_sess_token(cls, user_id):
        return 'this is a session token'

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
        if user_id not in cls.users: return False
        if conn_token != cls.conn_token: return False
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
    #endregion


    #region --- External 'Instance' Interface ---
    @classmethod
    def init(cls, client, users):
        """
        Parameters
        ----------
        client : Client
        users : tuple, list
            User IDs
        """
        cls.logger.info(f"Initializing WebSocket API with endpoint {client.websocket_endpoint}.")
        if cls.state >= SocketState.LIVE:
            raise ServerError(f"Cannot reconfigure WebSocket API during runtime.")
        
        cls.client = client
        cls.endpoint = client.websocket_endpoint
        cls.conn_token = cls.generate_conn_token()
        cls.state = SocketState.INIT
        for user in users: cls.users[user] = None
        cls.instance = cls()
        return cls.instance

    def run(self):
        cls = SocketAPI

        cls.logger.info(f"Starting WebSocket API.")
        if cls.state == SocketState.NEW:
            raise ServerError(f"Cannot start API before initialization.")
        if cls.state == SocketState.LIVE or cls.state == SocketState.OPEN:
            raise ServerError(f"Cannot start API: already running.")
        
        # cls.state = SocketState.LIVE # TODO: BE SURE TO UPDATE ON D/C OR SIMILAR
        # cls.socketio.run(cls.app, host=cls.endpoint.ip, port=cls.endpoint.port)

        while True:
            try:
                print(f"Serving WebSocket API at {cls.endpoint}")
                cls.logger.info(f"Serving WebSocket API at {cls.endpoint}")

                cls.state = SocketState.LIVE
                cls.socketio.run(cls.app, host=cls.endpoint.ip, port=cls.endpoint.port)
            except OSError as e:
                print(f"Listener endpoint {cls.endpoint} in use.")
                cls.logger.error(f"Endpoint {cls.endpoint} in use.")

                cls.state = SocketState.INIT
                cls.client.set_websocket_endpoint(Endpoint(cls.endpoint.ip, cls.endpoint.port + 1))
                continue
            cls.logger.info(f"WebSocket API terminated.")
            break

    @classmethod
    def kill(cls):
        cls.logger.info("Killing WebSocket API.")
        if not (cls.state == SocketState.LIVE or cls.state == SocketState.OPEN):
            raise ServerError(f"Cannot kill Client API when not {SocketState.LIVE} or {SocketState.OPEN}.")
        cls.socketio.stop() # "This method must be called from a HTTP or SocketIO handler function."
        cls.state = SocketState.INIT
        if cls.client.state == ClientState.CONNECTED:
            cls.client.state = ClientState.LIVE
    #endregion


    #region --- API Endpoints ---
    @socketio.on('connect') # TODO: Keep track of connection number. Our own
                            #       Client will (should) connect immediately...
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
            cls.logger.info(f"Socket connection failed authentication.")
            # raise UnknownRequester( ... ) # TODO: Maybe different name?
            # or 
            # raise ConnectionRefusedError( ... )
            return False
        
        sess_token = cls.generate_sess_token(user_id)
        cls.users[user_id] = sess_token
        cls.logger.info(f"Socket connection from User {user_id} accepted; yielding session token '{sess_token}'")
        emit('token', sess_token)

        if cls.has_all_users():
            cls.logger.info(f"Socket API acquired all expected users.")
            cls.client.state = ClientState.CONNECTED


    @socketio.on('message')
    @HandleExceptions
    def on_message(cls, auth, msg):
        user_id, sess_token = auth
        user_id = user_id
        cls.logger.info(f"Received message from User {user_id}: '{msg}'")
        if not cls.verify_sess_token(*auth):
            cls.logger.info(f"Authentication failed for User {user_id} with token '{sess_token}' at on_message.")
            return

        send((user_id,msg), broadcast=True)


    @socketio.on('disconnect')
    @HandleExceptions
    def on_disconnect(cls):
        cls.logger.info(f"Client disconnected.")
        if cls.client.state == ClientState.CONNECTED:
            cls.client.state = ClientState.LIVE
        # Broadcast to all clients to disconnect
        # Close all connections (if that's a thing)
        # Kill Web Socket
        # State returns to INIT
    #endregion
#endregion


#region --- Main ---
# TODO: Add Socket API; need a way to choose one or the other or both.
if __name__ == '__main__':
    from client import Client
    try:
        client = Client(websocket_endpoint=SocketAPI.DEFAULT_ENDPOINT)
        client.sess_token = 'abcdefg'
        instance = SocketAPI.init(client)
        instance.start() # Blocking
    except KeyboardInterrupt as e:
        logger.info("Intercepted Keyboard Interrupt.")
        ClientAPI.kill()
        SocketAPI.kill()
        logger.info("Exiting main program execution.\n")
        exit()
    except Exception as e:
        ClientAPI.kill()
        SocketAPI.kill()
        logger.error("Encountered unexpected exception.\n")
        raise e
#endregion