from flask import Flask, jsonify
from flask_sockets import Sockets
import logging

logging.basicConfig(filename='server.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__)
sockets = Sockets(app)

@app.route('/')
def hello():
  return "Hello, world!"

@sockets.route('/echo')
def echo(ws):
  while not ws.closed:
    message = ws.receive()
    ws.send(message)
    

if __name__ =='__main':
  app.run(debug=True)