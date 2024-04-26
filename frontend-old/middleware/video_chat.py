from client.client import Client, SocketClient
from client.api import ClientAPI
from client.utils import Endpoint
import socket
import json
import sys

import time

CONFIG = 'python_config.json'

if __name__ == "__main__":
  config = None
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
  
  peer_id = sys.argv[1]
  frontend_host = 'localhost'
  frontend_port = sys.argv[2]
  
  if (peer_id == None):
    input()
  else:
    frontend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    frontend_socket.bind((frontend_host, frontend_port))
    client.connect_to_peer(peer_id, frontend_socket)
    time.sleep(2)
    # At this point, SocketClient.init(...) has been called so AV namespaces are initialized and are at SocketClient.av