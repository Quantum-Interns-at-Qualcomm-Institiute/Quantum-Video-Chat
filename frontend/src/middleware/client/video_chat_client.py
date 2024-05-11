from typing import Optional
from client.api import ClientAPI
from client.endpoint import Endpoint
from client.errors import Errors
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
    def init(cls, endpoint: Endpoint, conn_token: str, user_id: str,
             display_message: callable, frontend_socket: Client):
        cls.logger.info(
            f"Initiailizing Socket Client with WebSocket endpoint {endpoint}.")

        cls.av = AVController(cls, frontend_socket)
        cls.namespaces = cls.av.client_namespaces

        cls.conn_token = conn_token  # TODO: remove
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
# endregion


# region --- Main Client ---

# TODO: consdier renaming to avoid confusion with Client
class VideoChatClient:
    # TODO: Remove websocket endpoint?
    def __init__(self):
        self.logger = logging.getLogger('Client')
        self.logger.info('Creating new Client')

        self.state = ClientState.NEW
        self.user_id = None
        self.sess_token = None  # TODO: Remove

        self.api_instance = ClientAPI.init(self)

        self.websocket_endpoint = None
        self.websocket_instance = None

        self.frontend_socket = None

        self.server_endpoint = None
        self.peer_endpoint = None

    def HandleClientExceptions(endpoint_handler: callable):
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

    # region --- Utils ---
    # @HandleClientExceptions
    def start_api(self, endpoint: Optional[Endpoint]):
        if endpoint:
            self.api_instance.set_endpoint(endpoint)
        elif self.api_instance.endpoint is None:
            raise Errors.INTERNALCLIENTERROR("Endpoint needed before starting API")
        self.api_instance.start()  # Start the API thread
        self.logger.info("Bound API endpoint to Client")

    # @HandleClientExceptions
    def set_server_endpoint(self, endpoint: Endpoint):
        if not endpoint:
            raise Errors.INTERNALCLIENTERROR(
                "Cannot connect to a server without an endpoint")

        # If already live this will prevent the rest
        self.set_state(ClientState.CONNECTING)
        self.server_endpoint = endpoint
        try:
            self.logger.info(f"Attempting to connect to server: {self.server_endpoint}.")
            response = self.contact_server('/create_user', json={
                'api_endpoint': tuple(self.api_instance.endpoint)
            })
        except Exception as e:
            self.server_endpoint = None  # Reset endpoint before exiting
            raise e

        # Makes sure response doesn't produce an error before setting the endpoint
        self.server_endpoint = endpoint
        self.user_id, self.sess_token = get_parameters(
            response.json(), 'user_id', 'sess_token')
        self.logger.info(f"Successfully connected to {self.server_endpoint} as ID '{self.user_id}' with session token '{self.sess_token}'.")
        self.set_state(ClientState.LIVE)

    # @HandleClientExceptions
    def set_frontend_socket(self, endpoint: Endpoint):
        if not endpoint:
            raise Errors.INTERNALCLIENTERROR(
                "Cannot connect to frontend without an endpoint")

        self.frontend_socket = Client()
        self.frontend_socket.connect(
            str(endpoint),
            headers={'user_id': self.user_id})

        self.logger.info(f"Bound frontend socket to {endpoint}")

    def connect_to_websocket(self, endpoint, conn_token):
        try:
            # TODO: figure out where to bubble down to
            sio = SocketClient.init(
                endpoint, conn_token, self.user_id,
                self.display_message, self.frontend_socket)
            sio.start()
        except Exception as e:
            self.logger.error(f"Failed to connect to WebSocket at {endpoint} with conn_token '{conn_token}'.")
            raise e

    def set_websocket_endpoint(self, endpoint: Endpoint):
        self.websocket_endpoint: Endpoint = endpoint
        self.logger.info(f"Bound websocket endpoint to {endpoint}")

    # TODO: should this have @HandleExceptions?

    def set_state(self, state: ClientState):
        if self.state > state:
            raise Errors.INTERNALCLIENTERROR(
                f"Cannot set state back to {state} or {self.state}")
        if self.state == state:
            raise Errors.INTERNALCLIENTERROR(f"State already set to {state}")
        self.state = state
        self.logger.info(f"Client's state set to {state}")

    # TODO: remove
    def authenticate_server(self, sess_token):
        return sess_token == self.sess_token

    def display_message(self, user_id, msg):
        print(f"({user_id}): {msg}")

    # @HandleClientExceptions
    def contact_server(self, route: str, json=None):
        endpoint = self.server_endpoint(route)
        self.logger.info(f"Contacting Server at {endpoint}.")

        response = requests.post(url=str(endpoint), json=json)

        if response.status_code != 200:
            raise Errors.UNEXPECTEDRESPONSE(f"Unexpected Server response at {endpoint}: {response.json()['details'] if 'details' in response.json() else response.reason}.")

        return response

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
        #  Delete the user from the server
        try:
            requests.delete(str(self.server_endpoint('/remove_user')), json={
                'user_id': self.user_id,
                'sess_token': self.sess_token  # TODO: Remove
            })
        except Exception:
            pass

    # endregion

    # region --- Server Interface ---
    # TODO: connect_to_server() returns a bool, but we never use it

    def connect_to_peer(self, peer_id: str):
        """
        Open Socket API. Contact Server /peer_connection with `conn_token`
        and await connection from peer (authenticated by `conn_token`).
        """
        # # TODO: move into config file
        # # TODO: implement testing mode
        # if peer_id == self.user_id:
        #     self.logger.info("Initiating test mode, mirroring video")

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
        pass
    # endregion

    # region --- Client API Handlers ---

    # TODO: Return case for failed connections

    def handle_peer_connection(self, peer_id, socket_endpoint, conn_token):
        """
        Initialize Socket Client and attempt
        connection to specified Socket API endpoint.
        Return `True` iff connection is successful

        Parameters
        ----------

        """
        if self.state == ClientState.CONNECTED:
            raise Errors.INTERNALCLIENTERROR(
                f"Cannot attempt peer websocket connection while {self.state}.")

        self.logger.info(f"Attempting to connect to peer {peer_id} at {socket_endpoint} with token '{conn_token}'.")

        try:
            self.connect_to_websocket(socket_endpoint, conn_token)
            return True
        except Exception as e:
            self.logger.info('Warning', f"Connection to incoming peer User {peer_id} failed because {e}")
            return False

    def disconnect_from_peer(self):
        pass
    # endregion

    # region --- Web Socket Interface ---

    # endregion
# endregion
