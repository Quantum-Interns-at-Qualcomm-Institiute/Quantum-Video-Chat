from client.video_chat_client import VideoChatClient
from client.endpoint import Endpoint
import json
import psutil
import platform

from client.encryption import EncryptSchemes, KeyGenerators
# import sys

DEV = True
CONFIG = f"{'dev_' if DEV else ''}python_config.json"

if __name__ == "__main__":
    with open(file=CONFIG) as json_data:
        config = json.load(json_data)

    api_port = config["API_ENDPOINT_PORT"]
    api_address = "localhost"

    search_string = ('Ethernet 2', 'en7') if config["AD_HOC"] else ('Wi-Fi', 'en0')
    for prop in psutil.net_if_addrs()[search_string[0 if platform.system() == 'Windows' else 1]]:
        if prop.family == 2:
            api_address = prop.address

    client = VideoChatClient().set_encryption_type(encryption_type=EncryptSchemes.AES).set_key_source(key_source=KeyGenerators.DEBUG)

    api_endpoint = Endpoint(ip=api_address, port=api_port)
    client.start_api(endpoint=api_endpoint)

    server_endpoint = Endpoint(ip=config["SERVER_IP"], port=config["SERVER_PORT"])
    client.set_server_endpoint(endpoint=server_endpoint)

    frontend_socket_endpoint = Endpoint(
        ip="localhost", port=5001)  # TODO: add back in the sys args
    client.set_frontend_socket(endpoint=frontend_socket_endpoint)

    @client.frontend_socket.on(event='connect_to_peer')
    def handle_conenct_to_peer(peer_id: str):
        print(f"Frontend reports peer ID {peer_id}")
        client.connect_to_peer(peer_id=peer_id)

    # TODO: this is a bit hacky, find a more elegant solution
    # This prevents the python process from terminating and closing the socket
    while True:
        # print("here")
        pass
