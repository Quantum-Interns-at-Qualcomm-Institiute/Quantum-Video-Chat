from client.client import Client
from client.endpoint import Endpoint
import json
import psutil
import platform
import sys

DEV = True
CONFIG = f"src/middleware/{'dev_' if DEV else ''}python_config.json"

if __name__ == "__main__":
    with open(CONFIG) as json_data:
        config = json.load(json_data)

    # TODO: This is hacky, may change in the future
    api_port = config["API_ENDPOINT_PORT"]
    api_address = "localhost"

    for prop in psutil.net_if_addrs()['WiFi 2' if platform.system() == 'Windows' else 'en0']:
        if prop.family == 2:
            api_address = prop.address

    def create_client():
        global api_port
        global api_address
        client = Client()

        try:
            api_endpoint = Endpoint(api_address, api_port)
            client.start_api(api_endpoint)
        except OSError:
            print(f"Port {api_port} in use, trying {api_port + 1}")
            api_port += 1
            create_client()

        server_endpoint = Endpoint(config["SERVER_IP"], config["SERVER_PORT"])
        client.set_server_endpoint(server_endpoint)

        frontend_socket_endpoint = Endpoint("localhost", 5001)
        client.set_frontend_socket(frontend_socket_endpoint)

        @client.frontend_socket.on('connect_to_peer')
        def handle_conenct_to_peer(peer_id: str):
            print(f"Frontend reports peer ID {peer_id}")
            # client.connect_to_peer(peer_id)

        return client

    client = create_client()

    # TODO: this is a bit hacky, find a more elegant solution
    # This prevents the python process from terminating and closing the socket
    while True:
        pass
