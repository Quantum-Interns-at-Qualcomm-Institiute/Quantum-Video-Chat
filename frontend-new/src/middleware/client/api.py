from flask import Flask, jsonify, request
from flask_socketio import SocketIO, send, emit
from flask_socketio import ConnectionRefusedError
from threading import Thread
# TODO: Look into usage for gevent
from gevent.pywsgi import WSGIServer # For asynchronous handling

from client.utils.av import TestFlaskNamespace, generate_flask_namespace

#region --- Logging ---
import logging
logging.basicConfig(filename='./client/logs/api.log', level=logging.DEBUG,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
#endregion


#region --- Utils ---
from client.utils import ClientState
from client.utils import Endpoint
from client.utils import get_parameters, is_type, remove_last_period
from client.utils import ServerError, BadGateway, BadRequest, ParameterError, InvalidParameter, BadAuthentication, UserNotFound

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
#endregion

import subprocess
import psutil
#region --- Client API ---
class ClientAPI(Thread):
    ip = '127.0.0.1'

    for prop in psutil.net_if_addrs()['en0']:
        if prop.family == 2:
            ip = prop.addr

    # TODO: Aaron commented this out because it was breaking stuff when testing python subprocesses of frontend main. Uncomment and fix later?
    # ip = subprocess.check_output(['ipconfig', 'getifaddr', 'en0']).strip().decode()
    DEFAULT_ENDPOINT = Endpoint(ip,4000) # TODO: Read from config, maybe?

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


#region --- Main ---
# TODO: Add Socket API; need a way to choose one or the other or both.
if __name__ == '__main__':
    from client import Client
    try:
        client = Client()
        client.sess_token = 'abcdefg'
    except KeyboardInterrupt as e:
        logger.info("Intercepted Keyboard Interrupt.")
        ClientAPI.kill()
        logger.info("Exiting main program execution.\n")
        exit()
    except Exception as e:
        ClientAPI.kill()
        logger.error("Encountered unexpected exception.\n")
        raise e
#endregion
