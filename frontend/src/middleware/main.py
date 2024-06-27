import json

import eventlet
from client.encryption import EncryptSchemes, KeyGenerators
from client.endpoint import Endpoint
from client.video_chat_client import VideoChatClientBuilder

# import sys

DEV = True
CONFIG = f"src/middleware/{'dev_' if DEV else ''}python_config.json"

DEFAULT_FRONTEND_PORT = 5001

if __name__ == "__main__":
    with open(file=CONFIG) as json_data:
        config = json.load(json_data)

    client_builder = VideoChatClientBuilder()\
        .set_encryption_scheme(encryption_scheme=EncryptSchemes.AES)\
        .set_key_source(key_source=KeyGenerators.DEBUG)\
        .set_server_endpoint(endpoint=Endpoint(ip=config["SERVER_IP"], port=config["SERVER_PORT"]))\
        .set_api_endpoint(endpoint=Endpoint(ip=config["API_ENDPOINT_IP"], port=config["API_ENDPOINT_PORT"]))\
        .set_frontend_endpoint(endpoint=Endpoint(ip=config["FRONTEND_ENDPOINT_IP"], port=config["FRONTEND_ENDPOINT_PORT"]))

    client = client_builder.build()

    client.setup()

    client.wait()

    # TODO: this is a bit hacky, find a more elegant solution
    # This prevents the python process from terminating and closing the socket
    while True:
        # print("here")
        eventlet.sleep(5)
