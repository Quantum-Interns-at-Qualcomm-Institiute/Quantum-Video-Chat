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

@app.route('/user/create', methods=['POST'])
def create_id():
  try:
      logger.info("Received request to create a user ID.")
      # TODO: Implement this function
      return jsonify({"error": "Not Implemented"}), 501
  except Exception as e:
      logger.error(f"An error occurred while creating user ID: {e}")
      return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500


@app.route('/user/retrieve', methods=['GET'])
def retrieve_id():
  try:
      logger.info("Received request to retrieve a user by ID.")
      # TODO: Implement this function
      return jsonify({"error": "Not Implemented"}), 501
  except Exception as e:
      logger.error(f"An error occurred while retreiving user ID: {e}")
      return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500


@app.route('/user/update', methods=['PUT'])
def update_id():
  try:
      logger.info("Received request to update user ID.")
      # TODO: Implement this function
      return jsonify({"error": "Not Implemented"}), 501
  except Exception as e:
      logger.error(f"An error occurred while updating user ID: {e}")
      return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500

@app.route('/user/delete', methods=['DELETE'])
def delete_id():
  try:
      logger.info("Received request to remove a user ID.")
      # TODO: Implement this function
      return jsonify({"error": "Not Implemented"}), 501
  except Exception as e:
      logger.error(f"An error occurred while removing user ID: {e}")
      return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500

@sockets.route('/echo')
def echo(ws):
  while not ws.closed:
    message = ws.receive()
    ws.send(message)
    

if __name__ =='__main':
  app.run(debug=True)