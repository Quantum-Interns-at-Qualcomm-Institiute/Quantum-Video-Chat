import json
import socketio
import sys

from client.client import Client
from client.api import ClientAPI
from client.endpoint import Endpoint
from custom_logging import logger

DEV = True
CONFIG = f"src/middleware/{'dev_' if DEV else ''}python_config.json"

if __name__ == "__main__":
    with open(CONFIG) as json_data:
        config = json.load(json_data)

    try:
        frontend_socket = socketio.Client()
        logger.info('Initializing client')
        client = Client(frontend_socket,
                        api_endpoint=ClientAPI.DEFAULT_ENDPOINT,
                        server_endpoint=Endpoint(config["SERVER_IP"],
                                                 config["SERVER_PORT"]))
        logger.info(f'Attempting to connect to frontend socket at {5001}')
        frontend_socket.connect(
            # f"http://localhost:{sys.argv[1]}",
            f"http://localhost:{5001}",
            headers={'user_id': client.user_id},
            retry=True)

        @frontend_socket.on('successfully_connected')
        def handle_successful_connection(data):
            logger.info(f'Successfully connected to frontend {data}')

        # TODO: convert back to lambda or not
        @frontend_socket.on('connect_to_peer')
        def handle_conenct_to_peer(data):
            logger.info(f'Received peer id {data} from frontend')
            client.connect_to_peer(data)

        while True:
            pass

    except Exception as f:
        raise f
