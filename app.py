from flask import Flask
from flask_sockets import Sockets

app = Flask(__name__)
sockets = Sockets(app)

@app.route('/')
def hello():
  return "Hello, world!"

@app.route('/user/create', methods=['POST'])
def create_id():
  id = ""
  return id, 501

@app.route('/user/retrieve', methods=['GET'])
def retrieve_id():
  id = ""
  return id, 501

@app.route('/user/update', methods=['PUT'])
def update_id():
  id = ""
  return id, 501

@app.route('/user/delete', methods=['DELETE'])
def delete_id():
  id = ""
  return id, 501



@sockets.route('/echo')
def echo(ws):
  while not ws.closed:
    message = ws.receive()
    ws.send(message)
    

if __name__ =='__main':
  app.run(debug=True)