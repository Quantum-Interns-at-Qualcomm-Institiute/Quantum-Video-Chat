from random import randrange, choice
import requests
from utils.user_manager import UserManager, UserStorageFactory, UserState
from utils.user_manager import DuplicateUser, UserNotFound
from exceptions import InvalidState

#region --- Logging --- # TODO: Add internal logger to Server class
import logging
logging.basicConfig(filename='./logs/server.log', level=logging.DEBUG,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
#endregion


#region --- Utils ---
from utils import Endpoint
from utils import get_parameters, is_type
from utils import ServerError, BadGateway, BadRequest, ParameterError, InvalidParameter, BadAuthentication
#endregion


#region --- Server ---
class Server:
    def __init__(self, api_endpoint, user_storage="DICT"):
        self.api_endpoint = Endpoint(*api_endpoint)
        self.logger = logging.getLogger('Server')
        self.logger.info(f"Intializing server with API Endpoint {self.api_endpoint}")
        
        with UserStorageFactory() as factory:
            storage = factory.create_storage(user_storage)
            self.user_manager = UserManager(storage=storage)
        self.qber_manager = None # QBERManager

    def verify_user(self, user_id, sess_token):
        try:
            user_info = self.get_user(user_id)
            return user_info.sess_token == sess_token
        except UserNotFound as e:
            return False
        
    def add_user(self, endpoint):
        try:
            user_id, sess_token = self.user_manager.add_user(endpoint)
            self.logger.info(f"User {user_id} added with sess_token '{sess_token}'.")
            return user_id, sess_token
        except DuplicateUser as e:
            self.logger.error(str(e))
            raise e

    def get_user(self, user_id):
        try:
            user_info = self.user_manager.get_user(user_id)
            self.logger.info(f"Retrieved user with ID {user_id}.")
            return user_info
        except UserNotFound as e:
            self.logger.error(str(e))
            raise e

    def remove_user(self, user_id):
        try:
            self.user_manager.remove_user(user_id)
            self.logger.info(f"User {user_id} removed successfully.")
        except UserNotFound as e:
            self.logger.error(str(e))
            raise e
        
    def set_user_state(self, user_id, state: UserState, peer= None):
        try:
            self.user_manager.set_user_state(user_id, state, peer)
            self.logger.info(f"Updated User {user_id} state: {state} ({peer}).")
        except (UserNotFound, InvalidState) as e:
            self.logger.error(str(e))
            raise e
        
    def contact_client(self, user_id, route, json):
        endpoint = self.get_user(user_id).api_endpoint(route)
        self.logger.info(f"Contacting Client API for User {user_id} at {endpoint}.")
        try:
            response = requests.post(str(endpoint), json=json)
        except Exception as e:
            self.logger.error(f"Unable to reach Client API for User {user_id} at endpoint {endpoint}.")
            raise e # TODO: Figure out specifically what exception is raised so I can catch only that, and then handle it instead of re-raising (or maybe re-raise different exception and then caller can handle)
        return response
        
    def handle_peer_connection(self, user_id, peer_id, websocket_endpoint, conn_token):
        if user_id == peer_id:
            raise BadRequest(f"Cannot intermediate connection between User {user_id} and self.")
        
        # TODO: Validate state(s)
        # if peer is not IDLE, reject
        try:
            user = self.get_user(user_id)
        except UserNotFound as e:
            raise BadRequest(f"User {user_id} does not exist.")
        try:
            peer = self.get_user(peer_id)
        except UserNotFound as e:
            raise BadRequest(f"User {peer_id} does not exist.")
        
        if peer.state != UserState.IDLE:
            raise InvalidState(f"Cannot connect to peer User {peer_id}: peer must be IDLE.")
        if user.state != UserState.IDLE:
            raise InvalidState(f"Cannot connect User {user_id} to peer: User must be IDLE.")
        
        self.logger.info(f"Contacting User {peer_id} to connect to User {user_id}.")
        try:
            response = self.contact_client(peer_id, '/peer_connection', json={
                'sess_token': self.get_user(peer_id).sess_token,
                'peer_id': user_id,
                'socket_endpoint': tuple(websocket_endpoint),
                'conn_token': conn_token
            })
        except Exception as e:
            raise BadGateway(f"Unable to reach peer User {peer_id}.")

        if response.status_code != 200:
            f"Peer User {peer_id} refused connection request."
            raise BadGateway(f"Peer User {peer_id} refused connection request.")
        self.logger.info(f"Peer User {peer_id} accepted connection request.")

#endregion

#region --- Main ---
if __name__ == "__main__":
    from api import ServerAPI
    server = Server(ServerAPI.DEFAULT_ENDPOINT)
#endregion