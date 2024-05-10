from client.video_chat_client import VideoChatClient
from client.endpoint import Endpoint
import json
import psutil
import platform
import sys

DEV = True
CONFIG = f"{'dev_' if DEV else ''}python_config.json"

if __name__ == "__main__":
    with open(CONFIG) as json_data:
        config = json.load(json_data)

    # TODO: This is hacky, may change in the future
    api_port = config["API_ENDPOINT_PORT"]
    api_address = "localhost"

    for prop in psutil.net_if_addrs()['Ethernet 2' if platform.system() == 'Windows' else 'en11']:
        if prop.family == 2:
            api_address = prop.address

    client = VideoChatClient()

    api_endpoint = Endpoint(api_address, api_port)
    client.start_api(api_endpoint)

    server_endpoint = Endpoint(config["SERVER_IP"], config["SERVER_PORT"])
    client.set_server_endpoint(server_endpoint)

    frontend_socket_endpoint = Endpoint(
        "localhost", 5001)  # TODO: add back in the sys args
    client.set_frontend_socket(frontend_socket_endpoint)

    @client.frontend_socket.on('connect_to_peer')
    def handle_conenct_to_peer(peer_id: str):
        print(f"Frontend reports peer ID {peer_id}")
        client.connect_to_peer(peer_id)

    # TODO: this is a bit hacky, find a more elegant solution
    # This prevents the python process from terminating and closing the socket
    while True:
        pass
