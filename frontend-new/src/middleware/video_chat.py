from client.client import Client
from client.api import ClientAPI
from client.utils import Endpoint
import socketio
import json
import sys

import time

CONFIG = 'src/middleware/python_config.json'

if __name__ == "__main__":
  with open(CONFIG) as json_data:
    config = json.load(json_data)

  try:
    frontend_port = sys.argv[1]
    frontend_socket = socketio.Client()

    client = Client(frontend_socket, api_endpoint=ClientAPI.DEFAULT_ENDPOINT)
    client.start_api()
    client.set_server_endpoint(Endpoint(config["SERVER_IP"], config["SERVER_PORT"]))
    client.connect()

    frontend_socket.connect(f"http://localhost:{frontend_port}", headers={'user_id' : client.user_id}, retry=True)

    @frontend_socket.on('connect_to_peer')
    def handle_conenct_to_peer(data):
      # data is peer's id
      client.connect_to_peer(data)


    while True:
      pass

  except Exception as f:
    raise f
