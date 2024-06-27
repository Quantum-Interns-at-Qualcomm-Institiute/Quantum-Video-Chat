
from datetime import datetime
from enum import Enum
from json import load as json_load
from logging import (
    DEBUG,
    WARN,
    FileHandler,
    Logger,
    StreamHandler,
    basicConfig,
    getLogger,
)
from threading import Thread

from encryption import EncryptSchemes, KeyGenerators
from eventlet import sleep
from exceptions import ClientErrors
from flask import Flask, jsonify, request
from gevent.pywsgi import WSGIServer
from namespaces import AVController
from requests import delete, post
from socketio import Client as SocketIOClient
from utils import APIState, ClientState, Endpoint, get_parameters, remove_last_period

DEV = True
DIR = 'src/middleware/refactored/'
CONFIG_FILE = f"./{DIR}{'dev_' if DEV else ''}python_config.json"
LOG_FILE = f'./{DIR}client.log'

basicConfig(level=DEBUG if DEV else WARN,
            format='[%(asctime)s] (%(levelname)s) %(name)s: %(message)s',
            datefmt='%H:%M:%S',
            handlers=[
                FileHandler(LOG_FILE),
                StreamHandler() if DEV else None
            ])

logger = getLogger(__name__)
logger.info(f"-----STARTING NEW LOGGING SESSION AT {datetime.now()}-----")

with open(file=CONFIG_FILE) as json_data:
    config = json_load(json_data)


class VideoChatClientBuilder:
    class Defaults(Enum):
        KEY_GEN: KeyGenerators = KeyGenerators.DEBUG
        WEBSOCKET_ENDPOINT: Endpoint = Endpoint('localhost', '25565')  # TODO: add default here
        ENCRYPTION_SCHEME: EncryptSchemes = EncryptSchemes.DEBUG
        SERVER_ENDPOINT: Endpoint = Endpoint('localhost', '25564')  # TODO: add default here
        FRONTEND_ENDPOINT: Endpoint = Endpoint('localhost', '25563')   # TODO: add default here
        API_ENDPOINT: Endpoint = Endpoint('localhost', '25562')  # TODO: add default here

    def __init__(self):
        self.logger = getLogger('VideoChatClientBuilder')
        self.logger.info("Setting up a new VideoChatClient")

        self.encryption_scheme: EncryptSchemes = None
        self.key_source: KeyGenerators = None

        self.api_endpoint: Endpoint = None
        self.frontend_endpoint: Endpoint = None
        self.server_endpoint: Endpoint = None
        self.websocket_endpoint: Endpoint = None

    def set_encryption_scheme(self, encryption_scheme: EncryptSchemes = None):
        self.encryption_scheme = encryption_scheme if encryption_scheme is not None else self.Defaults.ENCRYPTION_SCHEME

        self.logger.info(f"Client will use {self.encryption_scheme}-based encryption")

        return self

    def set_key_source(self, key_source: KeyGenerators = None):
        self.key_source = key_source if key_source is not None else self.Defaults.KEY_GEN

        self.logger.info(f"Client will use a {key_source}-source for key bits")

        return self

    def set_websocket_endpoint(self, endpoint: Endpoint = None):
        self.websocket_endpoint = endpoint if endpoint is not None else self.Defaults.WEBSOCKET_ENDPOINT  # TODO: add default endpoint

        self.logger.info(f"Setting Client's websocket endpoint to {self.websocket_endpoint}")

        return self

    def set_server_endpoint(self, endpoint: Endpoint = None):
        self.server_endpoint = endpoint if endpoint is not None else self.Defaults.SERVER_ENDPOINT

        self.logger.info(f"Setting Client's server endpoint to {self.server_endpoint}")

        return self

    def set_frontend_endpoint(self, endpoint: Endpoint = None):
        self.frontend_endpoint = endpoint if endpoint is not None else self.Defaults.FRONTEND_ENDPOINT

        self.logger.info(f"Setting VideoChatClient's frontend endpoint to {self.frontend_endpoint}")

        return self

    def set_api_endpoint(self, endpoint: Endpoint = None):
        self.api_endpoint = endpoint if endpoint is not None else self.Defaults.API_ENDPOINT

        self.logger.info(f"Setting VideoChatClient's API endpoint to  {self.api_endpoint}")

        return self

    def build(self):
        if self.encryption_scheme is None:
            raise BaseException("Must set encryption scheme before building client")
        if self.key_source is None:
            raise BaseException("Must set key source before building client")
        # TODO: do we need this?
        # if self.websocket_endpoint is None:
        #     raise BaseException("Must set client's websocket endpoint before building")
        if self.server_endpoint is None:
            raise BaseException("Must set client's server endpoint before building")
        if self.frontend_endpoint is None:
            raise BaseException("Must set client's frontend endpoint before building")

        self.logger.info("Creating new VideoChatClient")
        self.video_chat_client = VideoChatClient(encryption_scheme=self.encryption_scheme, key_source=self.key_source, server_endpoint=self.server_endpoint, websocket_endpoint=self.websocket_endpoint, frontend_endpoint=self.frontend_endpoint, api_endpoint=self.api_endpoint)
        return self.video_chat_client


class VideoChatClient:

    # TODO: Remove websocket endpoint?
    def __init__(self, encryption_scheme, key_source, server_endpoint, websocket_endpoint, frontend_endpoint, api_endpoint):
        self.logger = getLogger('VideoChatClient')

        self.video_chat_client_state = ClientState.NEW
        self.user_id = None
        self.sess_token = None  # TODO: Remove?

        self.api_instance = ClientAPI.init(self, endpoint=api_endpoint)  # TODO: where should this go/happen?

        self.websocket_endpoint: Endpoint = websocket_endpoint
        self.websocket_instance = None

        self.frontend_endpoint: Endpoint = frontend_endpoint
        self.frontend_sio_client: SocketClient = SocketIOClient()

        self.server_endpoint: Endpoint = server_endpoint
        self.peer_endpoint: Endpoint = None

        self.encryption_scheme: EncryptSchemes = encryption_scheme
        self.key_source: KeyGenerators = key_source

        self.logger.info("VideoChatClient has been created")
        self.set_state(ClientState.INITIALIZED)

    def set_state(self, new_state: ClientState):
        old_state = self.video_chat_client_state
        if old_state > new_state:
            raise ClientErrors.INTERNALCLIENTERROR(
                f"Cannot set state back to {new_state} or {self.video_chat_client_state}")
        if self.video_chat_client_state == new_state:
            raise ClientErrors.INTERNALCLIENTERROR(f"State already set to {new_state}")
        self.video_chat_client_state = new_state
        self.logger.info(f"VideoChatClient's state moved from {old_state} to {new_state}")

    def setup(self):
        if self.video_chat_client_state == ClientState.NEW:
            raise BaseException("Can only setup video chat client after initialization")
        if self.video_chat_client_state > ClientState.INITIALIZED:
            raise BaseException("Can only set up video chat client once")

        self.logger.info("Setting up VideoChatClient...")
        self.start_api()

        # TODO: place in a try-catch?
        self.connect_to_server_endpoint()

        self.connect_to_frontend_endpoint()
        self.logger.info("Finished setting up VideoChatClient!")
        self.set_state(ClientState.LIVE)

    def start_api(self):
        self.api_instance.start()  # Start the API thread
        self.logger.info("Started the VideoChatClient's API endpoint thread")

    # TODO: re-implement HandleClientExceptions

    def connect_to_server_endpoint(self):
        # If already live this will prevent the rest
        self.set_state(ClientState.CONNECTING)

        self.logger.info(f"Attempting to connect to server: {self.server_endpoint}...")
        response = self.contact_server('/create_user', json={
            'api_endpoint': tuple(self.api_instance.endpoint)
        })

        # Makes sure response doesn't produce an error before setting the client state
        self.user_id, self.sess_token = get_parameters(
            response.json(), 'user_id', 'sess_token')

        self.logger.info(f"Successfully connected to {self.server_endpoint} as ID '{self.user_id}' with session token '{self.sess_token}'!")
        # self.set_state(ClientState.LIVE)

    def wait(self):
        raise NotImplementedError

    def contact_server(self, route: str, json=None):
        endpoint_with_route = self.server_endpoint(route)
        self.logger.info(f"Contacting Server at {endpoint_with_route}.")

        response = post(url=str(endpoint_with_route), json=json)

        if response.status_code != 200:
            raise ClientErrors.UNEXPECTEDRESPONSE(f"Unexpected Server response at {endpoint_with_route}: {response.json()['details'] if 'details' in response.json() else response.reason}.")

        return response

    def connect_to_frontend_endpoint(self):
        # TODO: where should this best go?
        @self.frontend_sio_client.on(event='connect')
        def handle_connect():
            self.logger.info("Successfully connected to frontend socket")

        self.logger.info(f"Trying to connect to frontend endpoint at {self.frontend_endpoint}")

        # TODO: add a try-catch
        self.frontend_sio_client.connect(
            str(self.frontend_endpoint),
            headers={'user_id': self.user_id})

        self.logger.info(f"Connected to frontend socket at {self.frontend_endpoint}")

        # TODO: where should this best go?
        @self.frontend_sio_client.on(event='connect_to_peer')
        def handle_conenct_to_peer(peer_id: str):
            self.logger.info(f"Frontend reports a peer ID of {peer_id}")
            self.connect_to_peer(peer_id=peer_id)

    def connect_to_websocket(self, endpoint, conn_token):
        try:
            # TODO: find where this should best be located and if we can reduce what it does
            sio = SocketClient.init(
                endpoint=endpoint, conn_token=conn_token, user_id=self.user_id,
                display_message=self.display_message, frontend_socket=self.frontend_endpoint, encryption_type=self.encryption_scheme, key_source=self.key_source)
            sio.start()
        except Exception as e:
            self.logger.error(f"Failed to connect to WebSocket at {endpoint} with conn_token '{conn_token}'.")
            raise e

    # TODO: remove
    def authenticate_server(self, sess_token):
        return sess_token == self.sess_token

    # TODO: remove
    def display_message(self, user_id, msg):
        print(f"({user_id}): {msg}")

    def kill(self):
        # Shut down Client API
        try:
            ClientAPI.kill()
        except Exception:
            # TODO: handle what might have happend here
            pass

        # Close the Client's socket
        try:
            SocketClient.kill()
        except Exception:
            # TODO: handle what might have happend here
            pass

        # TODO: should this happen first?
        try:
            delete(str(self.server_endpoint('/remove_user')), json={
                'user_id': self.user_id,
                'sess_token': self.sess_token  # TODO: Remove
            })
        except Exception:
            pass

    def connect_to_peer(self, peer_id: str):
        """
        Open Socket API. Contact Server /peer_connection with `conn_token`
        and await connection from peer (authenticated by `conn_token`).
        """

        self.logger.info(
            f"Attempting to initiate connection to peer User {peer_id}.")

        response = self.contact_server('/peer_connection', json={
            'user_id': self.user_id,  # Requester's id
            'sess_token': self.sess_token,  # Requester's token
            'peer_id': peer_id,  # Host's id
        })

        # TODO: remove conn_token
        websocket_endpoint, conn_token = get_parameters(
            response.json(), 'socket_endpoint', 'conn_token')
        self.logger.info(f"Received websocket endpoint '{websocket_endpoint}' and conn_token '{conn_token}' from Server.")

        self.connect_to_websocket(websocket_endpoint, conn_token)
        while True:
            if SocketClient.is_connected():
                break

    def disconnect_from_server(self):
        return NotImplementedError

    # TODO: Return case for failed connections

    def handle_peer_connection(self, peer_id, socket_endpoint, conn_token):
        """
        Initialize Socket Client and attempt
        connection to specified Socket API endpoint.
        Return `True` iff connection is successful

        Parameters
        ----------

        """
        if self.video_chat_client_state == ClientState.CONNECTED:
            raise ClientErrors.INTERNALCLIENTERROR(
                f"Cannot attempt peer websocket connection while {self.video_chat_client_state}.")

        self.logger.info(f"Attempting to connect to peer {peer_id} at {socket_endpoint} with token '{conn_token}'.")

        try:
            self.connect_to_websocket(socket_endpoint, conn_token)
            return True
        except Exception as e:
            self.logger.info('Warning', f"Connection to incoming peer User {peer_id} failed because {e}")
            return False

    def disconnect_from_peer(self):
        pass


class ClientAPI(Thread):
    logger: Logger = getLogger('ClientAPI')
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
            raise ClientErrors.INTERNALCLIENTERROR(f"Cannot set state back to {new_state} or {cls.client_api_state}")
        if cls.client_api_state == new_state:
            raise ClientErrors.INTERNALCLIENTERROR(f"State already set to {new_state}")
        cls.client_api_state = new_state
        cls.logger.info(f"ClientAPI's state moved from {old_state} to {new_state}")

    @classmethod
    def run(cls):
        cls.logger.info("Starting ClientAPI...")

        if cls.client_api_state == APIState.NEW:
            raise ClientErrors.SERVERERROR("Cannot start API before initialization.")
        if cls.client_api_state == APIState.LIVE:
            raise ClientErrors.SERVERERROR("Cannot start API: already running.")

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
            raise ClientErrors.BADAUTHENTICATION(f"Authentication failed for server with token '{sess_token}'.")

    def HandleExceptions(func: callable):
        """
        Decorator to handle commonly encountered exceptions in the Client API

        NOTE: This should never be called explicitly
        """
        def wrapper(*args, **kwargs):
            cls = ClientAPI
            try:
                return func(cls, *args, **kwargs)
            except ClientErrors.BADAUTHENTICATION as e:
                return ClientErrors.BADAUTHENTICATION.info(remove_last_period(e))
            except ClientErrors.BADREQUEST as e:
                return ClientErrors.BADREQUEST.info(remove_last_period(e))
            except ClientErrors.SERVERERROR as e:
                return ClientErrors.SERVERERROR.info(remove_last_period(e))
            except ClientErrors.BADGATEWAY as e:
                return ClientErrors.BADGATEWAY.info(remove_last_period(e))
            except Exception as e:
                return ClientErrors.UNKNOWNERROR.info(remove_last_period(e))

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
            cls.logger.info("Responding with 418")
            return jsonify({"error_code": "418",
                            "error_message": "I'm a teapot",
                            "details": "Peer User refused connection"}), 418
        # TODO: What should we return?
        cls.logger.info("Responding with 200")
        return jsonify({'status_code': '200'}), 200


class SocketClient():
    sio: SocketIOClient = SocketIOClient()

    # region --- Utils ---
    logger = getLogger('SocketClient')

    @classmethod
    def set_sess_token(cls, sess_token):
        cls.logger.info(f"Setting session token '{sess_token}'")
        cls.sess_token = sess_token

    @classmethod
    def is_connected(cls):
        return cls.sio.connected

    def HandleExceptions(endpoint_handler: callable):
        """
        Decorator to handle commonly encountered
        exceptions at Socket Client endpoints.

        NOTE: This should never be called explicitly
        """
        def handler_with_exceptions(*args, **kwargs):
            cls = SocketClient

            try:
                return endpoint_handler(cls, *args, **kwargs)
            except Exception as e:  # TODO: Add excpetions
                raise e
        return handler_with_exceptions

    @classmethod
    # TODO: Unsure if client needed.
    def init(cls,
             endpoint: Endpoint,
             conn_token: str, user_id: str,
             display_message: callable,
             frontend_socket: SocketIOClient,
             encryption_type: EncryptSchemes.ABSTRACT, key_source: KeyGenerators.ABSTRACT):
        cls.logger.info(
            f"Initiailizing Socket Client with WebSocket endpoint {endpoint}.")

        cls.av = AVController(client_socket=cls, frontend_socket=frontend_socket, encryption_type=encryption_type, key_source=key_source)
        cls.namespaces = cls.av.client_namespaces

        cls.conn_token = conn_token
        cls.endpoint = Endpoint(*endpoint)
        cls.user_id = user_id
        cls.display_message = display_message
        cls.instance = cls()
        cls.sess_token = None
        return cls.instance

    def start(self):
        self.run()

    def run(self):
        SocketClient.connect()

    @classmethod
    def send_message(cls, msg: str, namespace='/'):
        cls.sio.send(((str(cls.user_id), cls.sess_token), msg),
                     namespace=namespace)

    @classmethod
    def connect(cls):
        cls.logger.info(f"Attempting WebSocket connection to {cls.endpoint} with connection token '{cls.conn_token}'.")
        ns = sorted(list(cls.namespaces.keys()))
        cls.sio.connect(str(cls.endpoint), wait_timeout=5, auth=(
            cls.user_id, cls.conn_token), namespaces=['/'] + ns)
        for name in ns:
            cls.sio.register_namespace(cls.namespaces[name])

    @classmethod
    def disconnect(cls):
        # Check to make sure we're actually connected
        cls.logger.info("Disconnecting Socket Client from Websocket API.")
        cls.sio.disconnect()
        # Make sure to update state, delete instance if necessary, etc.

    @classmethod
    def kill(cls):
        cls.logger.info("Killing Socket Client")
        cls.disconnect()
        # Make sure to update state, delete instance if necessary, etc.

    @sio.on('connect')
    def on_connect():
        cls = SocketClient
        cls.logger.info(f"Socket connection established to endpoint {SocketClient.endpoint}")
        ns = sorted(list(cls.namespaces.keys()))
        for name in ns:
            cls.namespaces[name].on_connect()

    @sio.on('token')
    def on_token(sess_token):
        cls = SocketClient
        cls.logger.info(f"Received session token '{sess_token}'")
        cls.set_sess_token(sess_token)

    @sio.on('message')
    def on_message(cls, user_id, msg):
        cls.logger.info(f"Received message from user {user_id}: {msg}")
        SocketClient.display_message(user_id, msg)


if __name__ == "__main__":
    # TODO: Make this part more like server's
    client_builder = VideoChatClientBuilder()\
        .set_encryption_scheme(encryption_scheme=EncryptSchemes.AES)\
        .set_key_source(key_source=KeyGenerators.DEBUG)\
        .set_server_endpoint(endpoint=Endpoint(ip=config["SERVER_IP"], port=config["SERVER_PORT"]))\
        .set_api_endpoint(endpoint=Endpoint(ip=config["API_ENDPOINT_IP"], port=config["API_ENDPOINT_PORT"]))\
        .set_frontend_endpoint(endpoint=Endpoint(ip=config["FRONTEND_ENDPOINT_IP"], port=config["FRONTEND_ENDPOINT_PORT"]))

    client = client_builder.build()

    client.setup()

    client.wait()

    # TODO: this is a bit hacky, find a more elegant solution
    # This prevents the python process from terminating and closing the socket
    while True:
        # print("here")
        sleep(5)
