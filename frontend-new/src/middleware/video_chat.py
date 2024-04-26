from client.client import Client, SocketClient
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

  client = Client(api_endpoint=ClientAPI.DEFAULT_ENDPOINT)
  client.start_api()

  try:
    server_endpoint = Endpoint(config["SERVER_IP"], config["SERVER_PORT"])

    try:
      client.set_server_endpoint(server_endpoint)
      client.connect()

    except Exception as e:
      raise e

  except Exception as f:
    raise f

  # TODO: Try-catch
  frontend_port = sys.argv[1]
  frontend_socket = socketio.Client()
  frontend_socket.connect(f"http://localhost:{frontend_port}", headers={'user_id' : client.user_id})

  @frontend_socket.on('connect_to_peer')
  def handle_conenct_to_peer(data):
    # data is peer's id
    client.connect_to_peer(data, frontend_socket)
