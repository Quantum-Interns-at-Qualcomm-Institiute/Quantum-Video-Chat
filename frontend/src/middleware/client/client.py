import requests
import socketio

from client.api import ClientAPI
from client.av import AV
from client.endpoint import Endpoint
from client.errors import Errors
from client.util import get_parameters, ClientState
from custom_logging import logger

# TODO: Trim down this file
# region --- Socket Client ---


class SocketClient():  # Not threaded because sio.connect() is not blocking

    sio = socketio.Client()
    user_id = None
    endpoint = None
    instance = None
    namespaces = None
    av = None
    video = {}
    display_message = None

    @classmethod
    def is_connected(cls):
        return cls.sio.connected

    def HandleExceptions(endpoint_handler):
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
    def init(cls, endpoint, user_id,
             display_message, frontend_socket):
        cls.logger.info(
            f"Initiailizing Socket Client with WebSocket endpoint {endpoint}.")

        cls.av = AV(cls, frontend_socket)
        cls.namespaces = cls.av.client_namespaces
        cls.endpoint = Endpoint(*endpoint)
        cls.user_id = user_id
        cls.display_message = display_message
        cls.instance = cls()
        return cls.instance

    def start(self):
        self.run()

    def run(self):
        SocketClient.connect()

    @classmethod
    def send_message(cls, msg: str, namespace='/'):
        cls.sio.send(((str(cls.user_id), ), msg),
                     namespace=namespace)

    @classmethod
    def connect(cls):
        cls.logger.info(f"Attempting WebSocket connection to {cls.endpoint}.")
        try:
            ns = sorted(list(cls.namespaces.keys()))
            cls.sio.connect(str(cls.endpoint), wait_timeout=5, auth=(
                cls.user_id), namespaces=['/'] + ns)
            for name in ns:
                cls.sio.register_namespace(cls.namespaces[name])
        except socketio.exceptions.ConnectionError as e:
            cls.logger.error(f"Connection failed: {str(e)}")

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
    @HandleExceptions
    def on_connect(cls):
        cls.logger.info(f"Socket connection established to endpoint {
                        SocketClient.endpoint}")
        ns = sorted(list(cls.namespaces.keys()))
        for name in ns:
            cls.namespaces[name].on_connect()

    @sio.on('message')
    @HandleExceptions
    def on_message(cls, user_id, msg):
        cls.logger.info(f"Received message from user {user_id}: {msg}")
        SocketClient.display_message(user_id, msg)

    # endregion
# endregion


# region --- Main Client ---


class Client:
    def __init__(self, frontend_socket, server_endpoint=None,
                 api_endpoint=None, websocket_endpoint=None):
        logger.info(f"""Initializing Client with:
                         Server endpoint {server_endpoint},
                         Client API endpoint {api_endpoint},
                         WebSocket API endpoint {websocket_endpoint}.""")
        self.user_id = None
        self.state = ClientState.NEW
        self.frontend_socket = frontend_socket
        self.server_endpoint = server_endpoint
        self.api_endpoint = api_endpoint
        self.websocket_endpoint = websocket_endpoint
        self.peer_endpoint = None
        self.api_instance = None
        self.websocket_instance = None

        self.gui = None
        self.start_api()
        self.connect()

    # region --- Utils ---

    # TODO: All endpoint functions should take a single endpoint obj.
    def set_server_endpoint(self, endpoint):
        if self.state >= ClientState.LIVE:
            # TODO: use InvalidState
            raise Errors.INTERNALCLIENTERROR.value(
                "Cannot change server endpoint after connection already established.")

        self.server_endpoint = Endpoint(*endpoint)
        logger.info(f"Setting server endpoint: {self.server_endpoint}")

    def set_api_endpoint(self, endpoint):
        if self.state >= ClientState.LIVE:
            # TODO: use InvalidState
            raise Errors.INTERNALCLIENTERROR.value(
                "Cannot change API endpoint after connection already established.")

        self.api_endpoint = Endpoint(*endpoint)
        ClientAPI.endpoint = self.api_endpoint
        logger.info(f"Setting API endpoint: {self.api_endpoint}")

    # TODO: duplicate method with one in util.py
    def display_message(self, user_id, msg):
        print(f"({user_id}): {msg}")

    def contact_server(self, route, json=None):
        endpoint = self.server_endpoint(route)
        logger.info(f"Contacting Server at {endpoint}.")

        try:
            response = requests.post(str(endpoint), json=json)
        except requests.exceptions.ConnectionError as e:
            raise Errors.CONNECTIONREFUSED.value(
                f"Unable to reach Server API at endpoint {endpoint}.")

        if response.status_code != 200:
            try:
                json = response.json()
            except requests.exceptions.JSONDecodeError as e:
                raise Errors.UNEXPECTEDRESPONSE.value(f"Unexpected Server response at {
                                                      endpoint}: {response.reason}.")

            context = response.json(
            )['details']if 'details' in response.json() else response.reason
            raise Errors.UNEXPECTEDRESPONSE.value(
                f"Unexpected Server response at {endpoint}: {context}.")
        return response

    def kill(self):
        try:
            ClientAPI.kill()
        except Exception:
            pass
        try:
            SocketClient.kill()
        except Exception:
            pass
        try:
            requests.delete(str(self.server_endpoint('/remove_user')), json={
                'user_id': self.user_id
            })
        except Exception:
            pass
        # TODO: Kill Socket Client
        # TODO: Kill Socket API
        # TODO: Kill Client API
        # TODO: Disconnect from server
        pass
    # endregion

    # region --- Server Interface ---
    # TODO: Client API should be LIVE first; need to give endpoint to server.

    def connect(self):
        """
        Attempt to connect to specified server.
        Expects token and user_id in return.
        Return `True` iff successful.
        """
        logger.info(f"Attempting to connect to server: {
                    self.server_endpoint}.")
        if (self.state >= ClientState.LIVE):
            logger.error(f"Cannot connect to {
                         self.server_endpoint}; already connected.")
            raise Errors.INTERNALCLIENTERROR.value(
                f"Cannot connect to {self.server_endpoint}; already connected.")

        try:
            response = self.contact_server('/create_user', json={
                'api_endpoint': tuple(self.api_endpoint)
            })
        except Errors.CONNECTIONREFUSED.value as e:
            logger.error(str(e))
            return False
        except Errors.UNEXPECTEDRESPONSE.value as e:
            logger.error(str(e))
            raise e

        try:
            self.user_id = get_parameters(
                response.json(), 'user_id')
            logger.info(f"Received user_id '{self.user_id}'.")
        except Errors.PARAMETERERROR.value as e:
            context = f"Server response did not contain user_id at {
                self.server_endpoint('/create_user')}."
            logger.error(context)
            raise Errors.UNEXPECTEDRESPONSE.value(context)

        self.state = ClientState.LIVE
        logger.info(f"Received user_id {self.user_id}")
        return True

    def connect_to_peer(self, peer_id):
        """
        Open Socket API. Contact Server /peer_connection and await connection from peer
        """
        logger.info(
            f"Attempting to initiate connection to peer User {peer_id}.")
        try:
            response = self.contact_server('/peer_connection', json={
                'user_id': self.user_id,
                'peer_id': peer_id,
            })
        except Errors.CONNECTIONREFUSED.value as e:
            logger.error(str(e))
            raise e
        except Errors.UNEXPECTEDRESPONSE.value as e:
            logger.error(str(e))
            raise e

        websocket_endpoint = get_parameters(
            response.json(), 'socket_endpoint')
        logger.info(f"Received websocket endpoint '{
            websocket_endpoint}'.")
        self.connect_to_websocket(websocket_endpoint)
        while True:
            if SocketClient.is_connected():
                break

    def disconnect_from_server(self):
        pass
    # endregion

    # region --- Client API Handlers ---

    def start_api(self):
        if not self.api_endpoint:
            raise Errors.INTERNALCLIENTERROR.value(
                "Cannot start Client API without defined endpoint.")

        self.api_instance = ClientAPI.init(self)
        self.api_instance.start()

    # TODO: Return case for failed connections
    def handle_peer_connection(self, peer_id, socket_endpoint):
        """
        Initialize Socket Client and attempt
        connection to specified Socket API endpoint.
        Return `True` iff connection is successful

        Parameters
        ----------

        """
        if self.state == ClientState.CONNECTED:
            raise Errors.INTERNALCLIENTERROR.value(
                f"Cannot attempt peer websocket connection while {self.state}.")

        logger.info("Polling User")
        print(f"Incoming connection request from {peer_id}.")
        logger.info("User Accepted Connection.")
        logger.info(f"Attempting to connect to peer {
            peer_id} at {socket_endpoint}.")

        try:
            self.connect_to_websocket(socket_endpoint)
            return True
        except Exception as e:
            logger.error('Warning', f"Connection to incoming peer User {
                         peer_id} failed.")
            return False

    def disconnect_from_peer(self):
        pass
    # endregion

    # region --- Web Socket Interface ---
    def connect_to_websocket(self, endpoint):
        sio = SocketClient.init(
            endpoint, self.user_id,
            self.display_message, self.frontend_socket)
        try:
            sio.start()
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket at {endpoint}.")
            raise e
    # endregion
# endregion
