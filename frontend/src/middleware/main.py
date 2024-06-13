from client.video_chat_client import VideoChatClient
from client.endpoint import Endpoint
import eventlet
import json
import psutil
import platform

from client.encryption import EncryptSchemes, KeyGenerators

import sys

DEV = True
import os
CONFIG = f"src/middleware/{'dev_' if DEV else ''}python_config.json"

DEFAULT_FRONTEND_PORT = 5001

if __name__ == "__main__":
    client = VideoChatClient().set_encryption_type(encryption_type=EncryptSchemes.AES).set_key_source(key_source=KeyGenerators.DEBUG)

    # Connect to frontend process through socket
    FRONTEND_PORT = DEFAULT_FRONTEND_PORT
    if sys.argv[1]: FRONTEND_PORT = sys.argv[1]
    frontend_socket_endpoint = Endpoint(
        ip="localhost", port=FRONTEND_PORT)
    client.set_frontend_socket(endpoint=frontend_socket_endpoint)

    with open(file=CONFIG) as json_data:
        config = json.load(json_data)

    api_port = config["API_ENDPOINT_PORT"]
    api_address = "localhost"

    search_string = ('Ethernet 2', 'en11') if config["AD_HOC"] else ('Wi-Fi', 'en0')
    for prop in psutil.net_if_addrs()[search_string[0 if platform.system() == 'Windows' else 1]]:
        if prop.family == 2:
            api_address = prop.address

    api_endpoint = Endpoint(ip=api_address, port=api_port)
    client.start_api(endpoint=api_endpoint)

    server_endpoint = Endpoint(ip=config["SERVER_IP"], port=config["SERVER_PORT"])
    client.set_server_endpoint(endpoint=server_endpoint)

    # Communicate self id to frontend
    print(f"Emitting self_id {client.user_id} to frontend.")
    client.frontend_socket.emit('self_id', data=client.user_id)

    @client.frontend_socket.on(event='connect_to_peer')
    def handle_conenct_to_peer(peer_id: str):
        print(f"Frontend reports peer ID {peer_id}")
        client.connect_to_peer(peer_id=peer_id)

    # TODO: this is a bit hacky, find a more elegant solution
    # This prevents the python process from terminating and closing the socket
    while True:
        # print("here")
        eventlet.sleep(5)
