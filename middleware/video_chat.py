import json
import os as _os
import sys

# Add project root to path so `shared` is importable
_project_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

import socketio

from client.client import Client
from client.api import ClientAPI
from adapters.electron import ElectronSocketAdapter
from shared.endpoint import Endpoint
from shared.config import ELECTRON_IPC_PORT
from custom_logging import logger

DEV = True
_dir = _os.path.dirname(_os.path.abspath(__file__))
CONFIG = _os.path.join(_dir, f"{'dev_' if DEV else ''}python_config.json")

if __name__ == "__main__":
    with open(CONFIG) as json_data:
        config = json.load(json_data)

    try:
        frontend_socket = socketio.Client()
        adapter = ElectronSocketAdapter(frontend_socket)

        # Connect to Electron's IPC socket first so that status events emitted
        # during Client initialisation (server_connecting, server_connected, …)
        # are delivered to the frontend.
        logger.info(f'Attempting to connect to frontend socket at {ELECTRON_IPC_PORT}')
        frontend_socket.connect(
            f"http://localhost:{ELECTRON_IPC_PORT}",
            retry=True,
            transports=['websocket'])

        @frontend_socket.on('successfully_connected')
        def handle_successful_connection(data):
            logger.info(f'Successfully connected to frontend {data}')

        logger.info('Initializing client')
        client = Client(adapter,
                        api_endpoint=ClientAPI.DEFAULT_ENDPOINT,
                        server_endpoint=Endpoint(config["SERVER_IP"],
                                                 config["SERVER_PORT"]))

        adapter.on_peer_id(client.connect_to_peer)

        @frontend_socket.on('disconnect_call')
        def handle_disconnect_call():
            logger.info('Received disconnect_call from frontend.')
            client.disconnect_from_peer()

        @frontend_socket.on('toggle_mute')
        def handle_toggle_mute():
            from client.socket_client import SocketClient
            if SocketClient.av is not None:
                SocketClient.av.mute_audio = not SocketClient.av.mute_audio
                logger.info(f'Mute toggled: {SocketClient.av.mute_audio}')
                adapter.send_status('mute_changed', {'muted': SocketClient.av.mute_audio})

        try:
            frontend_socket.wait()
        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received — shutting down.')
        finally:
            client.kill()
            frontend_socket.disconnect()

    except Exception as f:
        raise f
