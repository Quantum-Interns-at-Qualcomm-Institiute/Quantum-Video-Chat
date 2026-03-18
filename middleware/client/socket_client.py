import socketio

from client.av import AV
from client.endpoint import Endpoint
from shared.adapters import FrontendAdapter
from custom_logging import logger


# region --- Socket Client ---

class SocketClient:  # Not threaded because sio.connect() is not blocking

    def __init__(self, endpoint, user_id, display_message, adapter: FrontendAdapter,
                 session_settings=None):
        logger.info(f"Initializing Socket Client with WebSocket endpoint {endpoint}.")
        self.sio = socketio.Client()
        self.user_id = user_id
        self.endpoint = Endpoint(*endpoint)
        self.display_message = display_message
        self.video = {}

        self.av = AV(self, adapter, session_settings=session_settings)
        self.namespaces = self.av.client_namespaces

        # Register event handlers on this instance's sio
        self.sio.on('connect')(self._on_connect)
        self.sio.on('message')(self._on_message)

    # region --- External Interface ---

    def is_connected(self):
        return self.sio.connected

    def start(self):
        self.connect()

    def send_message(self, msg: str, namespace='/'):
        self.sio.send(((str(self.user_id),), msg), namespace=namespace)

    def connect(self):
        if self.sio.connected:
            logger.info("WebSocket already connected — skipping duplicate connect.")
            return
        logger.info(f"Attempting WebSocket connection to {self.endpoint}.")
        try:
            ns = sorted(list(self.namespaces.keys()))
            for name in ns:
                self.sio.register_namespace(self.namespaces[name])
            self.sio.connect(str(self.endpoint), wait_timeout=5, auth=(
                self.user_id), namespaces=['/'] + ns,
                transports=['websocket'])
        except socketio.exceptions.ConnectionError as e:
            logger.error(f"Connection failed: {str(e)}")

    def disconnect(self):
        logger.info("Disconnecting Socket Client from Websocket API.")
        self.sio.disconnect()

    def kill(self):
        logger.info("Killing Socket Client")
        self.disconnect()

    # endregion

    # region --- Event Handlers ---

    def _on_connect(self):
        logger.info(f"Socket connection established to endpoint {self.endpoint}")

    def _on_message(self, user_id, msg):
        logger.info(f"Received message from user {user_id}: {msg}")
        self.display_message(user_id, msg)

    # endregion

# endregion
