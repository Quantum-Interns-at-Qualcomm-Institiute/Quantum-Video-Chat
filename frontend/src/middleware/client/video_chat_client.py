from enum import Enum
from client.api import ClientAPI
from client.endpoint import Endpoint
from client.errors import Errors
from client.encryption import EncryptSchemes, KeyGenerators
from client.util import get_parameters, ClientState
from client.namespaces.av_controller import AVController
# from client.decorators import HandleExceptions as HandleClientExceptions
import requests
from socketio import Client

# region --- Logging --- # TODO: Add internal logger to Client class
import logging

# XXX: Switch back to level=logging.DEBUG
logging.basicConfig(filename='./src/middleware/logs/client.log',
                    level=logging.INFO,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
# endregion

# TODO: Trim down this file
# region --- Socket Client ---

# TODO: Why can't this be an object?


class SocketClient():
    sio: Client = Client()

    # def __init__(self):
    #     self.user_id: str = None
    #     self.endpoint: Endpoint = None
    #     self.conn_token = None
    #     self.sess_token = None
    #     self.instance = None
    #     self.namespaces = None
    #     self.av = None
    #     self.video = {}
    #     self.display_message = None

    # region --- Utils ---
    logger = logging.getLogger('SocketClient')

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
    # endregion

    # region --- External Interface ---

    @classmethod
    # TODO: Unsure if client needed.
    def init(cls,
             endpoint: Endpoint,
             conn_token: str, user_id: str,
             display_message: callable,
             frontend_socket: Client,
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
    # endregion

    # region --- Event Endpoints ---

    @sio.on('connect')
    # @HandleExceptions
    def on_connect():
        cls = SocketClient
        cls.logger.info(f"Socket connection established to endpoint {SocketClient.endpoint}")
        ns = sorted(list(cls.namespaces.keys()))
        for name in ns:
            cls.namespaces[name].on_connect()

    @sio.on('token')
    # @HandleExceptions
    def on_token(sess_token):
        cls = SocketClient
        cls.logger.info(f"Received session token '{sess_token}'")
        cls.set_sess_token(sess_token)

    @sio.on('message')
    # @HandleExceptions
    def on_message(cls, user_id, msg):
        cls.logger.info(f"Received message from user {user_id}: {msg}")
        SocketClient.display_message(user_id, msg)

    # endregion


class VideoChatClientBuilder:
    class Defaults(Enum):
        KEY_GEN: KeyGenerators = KeyGenerators.DEBUG
        WEBSOCKET_ENDPOINT: Endpoint = Endpoint('localhost', '25565')  # TODO: add default here
        ENCRYPTION_SCHEME: EncryptSchemes = EncryptSchemes.DEBUG
        SERVER_ENDPOINT: Endpoint = Endpoint('localhost', '25564')  # TODO: add default here
        FRONTEND_ENDPOINT: Endpoint = Endpoint('localhost', '25563')   # TODO: add default here
        API_ENDPOINT: Endpoint = Endpoint('localhost', '25562')  # TODO: add default here

    def __init__(self):
        self.logger = logging.getLogger('VideoChatClientBuilder')
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
        self.logger = logging.getLogger('VideoChatClient')

        self.video_chat_client_state = ClientState.NEW
        self.user_id = None
        self.sess_token = None  # TODO: Remove?

        self.api_instance = ClientAPI.init(self, endpoint=api_endpoint)  # TODO: where should this go/happen?

        self.websocket_endpoint: Endpoint = websocket_endpoint
        self.websocket_instance = None

        self.frontend_endpoint: Endpoint = frontend_endpoint
        self.frontend_sio_client: SocketClient = Client()

        self.server_endpoint: Endpoint = server_endpoint
        self.peer_endpoint: Endpoint = None

        self.encryption_scheme: EncryptSchemes = encryption_scheme
        self.key_source: KeyGenerators = key_source

        self.logger.info("VideoChatClient has been created")
        self.set_state(ClientState.INITIALIZED)

    def set_state(self, new_state: ClientState):
        old_state = self.video_chat_client_state
        if old_state > new_state:
            raise Errors.INTERNALCLIENTERROR(
                f"Cannot set state back to {new_state} or {self.video_chat_client_state}")
        if self.video_chat_client_state == new_state:
            raise Errors.INTERNALCLIENTERROR(f"State already set to {new_state}")
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
        self.logger.log("Finished setting up VideoChatClient!")
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
        self.set_state(ClientState.LIVE)

    def wait(self):
        raise NotImplementedError

    def contact_server(self, route: str, json=None):
        endpoint_with_route = self.server_endpoint(route)
        self.logger.info(f"Contacting Server at {endpoint_with_route}.")

        response = requests.post(url=str(endpoint_with_route), json=json)

        if response.status_code != 200:
            raise Errors.UNEXPECTEDRESPONSE(f"Unexpected Server response at {endpoint_with_route}: {response.json()['details'] if 'details' in response.json() else response.reason}.")

        return response

    def connect_to_frontend_endpoint(self):
        # TODO: where should this best go?
        @self.frontend_sio_client.on(event='connect')
        def handle_connect():
            self.logger.log("Successfully connected to frontend socket")

        self.logger.log(f"Trying to connect to frontend endpoint at {self.frontend_endpoint}")

        # TODO: add a try-catch
        self.frontend_sio_client.connect(
            str(self.frontend_endpoint),
            headers={'user_id': self.user_id})

        self.logger.info(f"Connected to frontend socket at {self.frontend_endpoint}")

        # TODO: where should this best go?
        @self.frontend_sio_client.on(event='connect_to_peer')
        def handle_conenct_to_peer(peer_id: str):
            self.logger.log(f"Frontend reports a peer ID of {peer_id}")
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
            requests.delete(str(self.server_endpoint('/remove_user')), json={
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
            raise Errors.INTERNALCLIENTERROR(
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
