from flask import Flask, jsonify, request
from server.main_server import Server, DuplicateUser, UserNotFound
import logging
from gevent.pywsgi import WSGIServer  # For asynchronous handling
import configparser  # For reading configuration file

# Initialize logging
logging.basicConfig(filename='server_api.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Read API endpoints from a configuration file
config = configparser.ConfigParser()
config.read('api_endpoints.ini')

app = Flask(__name__)
server_instance = Server(host='localhost', port=5000)

async def handle_request(request_type, url, **kwargs):
    try:
        if request_type == 'POST':
            response = await request.post(url, **kwargs)
        elif request_type == 'GET':
            response = await request.get(url, **kwargs)
        elif request_type == 'DELETE':
            response = await request.delete(url, **kwargs)
        # TODO: Flesh out more request types to match code needs

        if response.status_code in [200, 201, 204]:
            return response.json(), response.status_code
        else:
            logger.error(f"Failed API call. Status code: {response.status_code}")
            return None, response.status_code
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None, 500


@app.route(config['API']['create_user'], methods=['POST'])
async def create_user():
    data, status_code = await handle_request('POST', f"{config['API']['create_user']}", json=request.json)
    return jsonify(data), status_code
  # try:
  #     logger.info("Received request to create a user ID.")
  #     # TODO: Implement this function
  #     return jsonify({"error": "Not Implemented"}), 501
  # except Exception as e:
  #     logger.error(f"An error occurred while creating user ID: {e}")
  #     return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500


@app.route(config['API']['retrieve_user'], methods=['GET'])
async def retrieve_user(user_id):
  data, status_code = await handle_request('GET', f"{config['API']['retrieve_user']}/{user_id}")
  return jsonify(data), status_code
  # try:
  #     logger.info("Received request to retrieve a user by ID.")
  #     # TODO: Implement this function
  #     return jsonify({"error": "Not Implemented"}), 501
  # except Exception as e:
  #     logger.error(f"An error occurred while retreiving user ID: {e}")
  #     return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500


# @app.route('/user/update', methods=['PUT'])
# def update_id():
#   try:
#       logger.info("Received request to update user ID.")
#       # TODO: Implement this function
#       return jsonify({"error": "Not Implemented"}), 501
#   except Exception as e:
#       logger.error(f"An error occurred while updating user ID: {e}")
#       return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500

@app.route(config['API']['remove_user'], methods=['DELETE'])
async def remove_user(user_id):
    data, status_code = await handle_request('DELETE', f"{config['API']['remove_user']}/{user_id}")
    return jsonify(data), status_code
#   try:
#       logger.info("Received request to remove a user ID.")
#       # TODO: Implement this function
#       return jsonify({"error": "Not Implemented"}), 501
#   except Exception as e:
#       logger.error(f"An error occurred while removing user ID: {e}")
#       return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500


# @app.route('/security/configure', methods=['POST'])
# def configure_security():
#     try:
#         logger.info("Received request to configure security.")
#         # TODO: Implement this function
#         return jsonify({"error": "Not Implemented"}), 501
#     except Exception as e:
#         logger.error(f"An error occurred while configuring security: {e}")
#         return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500

# @app.route('/security/key/initiate_exchange', methods=['POST'])
# def initiate_key_exchange():
#     try:
#         logger.info("Received request to initiate key exchange.")
#         # TODO: Implement this function
#         return jsonify({"error": "Not Implemented"}), 501
#     except Exception as e:
#         logger.error(f"An error occurred while initiating key exchange: {e}")
#         return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500

@app.route('/tools/health_check', methods=['GET'])
def health_check():
    try:
        logger.info("Received health check request.")
        return jsonify({"status": "OK"}), 200
    except Exception as e:
        logger.error(f"An error occurred during the health check: {e}")
        return jsonify({"error_code": "500", "error_message": "Internal Server Error", "details": str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting the server.")
    http_server = WSGIServer(('0.0.0.0', 5000), app)
    http_server.serve_forever()