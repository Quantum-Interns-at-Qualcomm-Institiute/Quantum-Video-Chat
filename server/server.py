from enum import Enum
from functools import total_ordering
from typing import Tuple
from user import User
from utils import ServerError, BadGateway, BadRequest
from utils import Endpoint
import requests
from utils.user_manager import UserManager, UserStorageFactory, UserState
from utils.user_manager import DuplicateUser, UserNotFound
from exceptions import InvalidState

# region --- Logging --- # TODO: Add internal logger to Server class
import logging
logging.basicConfig(filename='./logs/server.log', level=logging.DEBUG,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
# endregion


# region --- Utils ---
# endregion

@total_ordering
class SocketState(Enum):
    NEW = 'NEW'
    INIT = 'INIT'
    LIVE = 'LIVE'
    OPEN = 'OPEN'

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented
# region --- Server ---


class Server:
    def __init__(self, api_endpoint: Endpoint, SocketAPI, SocketState: SocketState, user_storage="DICT"):
        # TODO: GET RID OF THIS AND FIX IT LATER OMG THIS IS DISGUSTING
        # the socket api should start in main with the server api...
        self.SocketAPI = SocketAPI
        self.SocketState = SocketState

        self.api_endpoint = Endpoint(*api_endpoint)
        self.logger = logging.getLogger('Server')
        self.logger.info(f"Intializing server with API Endpoint {
                         self.api_endpoint}")

        self.websocket_endpoint = SocketAPI.DEFAULT_ENDPOINT
        self.user_manager = UserManager(
            storage=UserStorageFactory().create_storage(user_storage))

        self.qber_manager = None  # QBERManager

    def verify_user(self, user_id: str, sess_token: str):
        try:
            user = self.get_user(user_id)
            return user.sess_token == sess_token
        except UserNotFound:
            return False

    def add_user(self, endpoint):
        try:
            user_id, sess_token = self.user_manager.add_user(endpoint)
            self.logger.info(
                f"User {user_id} added with sess_token '{sess_token}'.")
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

    def set_user_state(self, user_id, state: UserState, peer=None):
        try:
            self.user_manager.set_user_state(user_id, state, peer)
            self.logger.info(f"Updated User {user_id} state: {
                             state} ({peer}).")
        except (UserNotFound, InvalidState) as e:
            self.logger.error(str(e))
            raise e

    def contact_client(self, user_id, route, json):
        endpoint = self.get_user(user_id).api_endpoint(route)
        self.logger.info(f"Contacting Client API for User {
                         user_id} at {endpoint}.")
        try:
            response = requests.post(str(endpoint), json=json)
        except Exception as e:
            self.logger.error(f"Unable to reach Client API for User {
                              user_id} at endpoint {endpoint}.")
            # TODO: Figure out specifically what exception is raised so I can catch only that,
            # and then handle it instead of re-raising
            # (or maybe re-raise different exception and then caller can handle)
            raise e
        return response

    def set_websocket_endpoint(self, endpoint):
        self.websocket_endpoint = Endpoint(*endpoint)
        self.SocketAPI.endpoint = self.websocket_endpoint
        self.logger.info(f"Setting Web Socket endpoint: {
                         self.websocket_endpoint}")

    def start_websocket(self, users: Tuple[User, User]):
        self.logger.info("Starting WebSocket API.")
        if not self.websocket_endpoint:
            raise ServerError(
                "Cannot start WebSocket API without defined endpoint.")

        self.websocket_instance = self.SocketAPI.init(self, users)
        self.websocket_instance.start()

    def handle_peer_connection(self, user_id: str, peer_id: str):
        if user_id == peer_id:
            raise BadRequest(f"Cannot intermediate connection between User {
                             user_id} and self.")

        # TODO: Validate state(s)
        # if peer is not IDLE, reject
        try:
            requester = self.get_user(user_id)
        except UserNotFound:
            raise BadRequest(f"User {user_id} does not exist.")
        try:
            host = self.get_user(peer_id)
        except UserNotFound:
            raise BadRequest(f"User {peer_id} does not exist.")

        if host.state != UserState.IDLE:
            raise InvalidState(f"Cannot connect to peer User {
                               peer_id}: peer must be IDLE.")
        if requester.state != UserState.IDLE:
            raise InvalidState(f"Cannot connect User {
                               user_id} to peer: User must be IDLE.")

        self.logger.info(f"Contacting User {
                         peer_id} to connect to User {user_id}.")

        self.start_websocket(users=(requester, host))

        try:
            response = self.contact_client(peer_id, '/peer_connection', json={
                'sess_token': host.sess_token,
                'peer_id': requester.id,
                'socket_endpoint': tuple(self.websocket_endpoint),
                'conn_token': self.SocketAPI.conn_token
            })
        except Exception:
            raise BadGateway(f"Unable to reach peer User {peer_id}.")
        print(f"Status code: {response.status_code}")
        if response.status_code != 200:
            f"Peer User {peer_id} refused connection request."
            raise BadGateway(
                f"Peer User {peer_id} refused connection request.")
        self.logger.info(f"Peer User {peer_id} accepted connection request.")
        return self.websocket_endpoint, self.SocketAPI.conn_token

# endregion


# region --- Main ---
if __name__ == "__main__":
    from api import ServerAPI
    # NOTE: This doesn't have the correct arguments now; not important, though
    server = Server(ServerAPI.DEFAULT_ENDPOINT)
# endregion
