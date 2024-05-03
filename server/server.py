import requests

from exceptions import InvalidState

from custom_logging import logger
from utils import ServerError, BadGateway, BadRequest, Endpoint
from utils.user_manager import UserManager, UserStorageFactory, UserState
from utils.user_manager import DuplicateUser, UserNotFound


# region --- Server ---
class Server:
    # TODO: make user storage type pull from config file
    def __init__(self, api_endpoint, SocketAPI, SocketState, user_storage="DICT"):
        # TODO: GET RID OF THIS AND FIX IT LATER OMG THIS IS DISGUSTING
        # the socket api should start in main with the server api...
        self.SocketAPI = SocketAPI
        self.SocketState = SocketState

        self.api_endpoint = Endpoint(*api_endpoint)
        logger.info(f"Intializing server with API Endpoint {
            self.api_endpoint}")

        self.websocket_endpoint = SocketAPI.DEFAULT_ENDPOINT

        with UserStorageFactory() as factory:
            storage = factory.create_storage(user_storage)
            self.user_manager = UserManager(storage=storage)
        self.qber_manager = None  # QBERManager

    def add_user(self):
        try:
            user_id = self.user_manager.add_user()
            logger.info(f"User {user_id} added.")
            return user_id
        except DuplicateUser as e:
            logger.error(str(e))
            raise e

    def get_user(self, user_id):
        try:
            user_info = self.user_manager.get_user(user_id)
            logger.info(f"Retrieved user with ID {user_id}.")
            return user_info
        except UserNotFound as e:
            logger.error(str(e))
            raise e

    def remove_user(self, user_id):
        try:
            self.user_manager.remove_user(user_id)
            logger.info(f"User {user_id} removed successfully.")
        except UserNotFound as e:
            logger.error(str(e))
            raise e

    def set_user_state(self, user_id, state: UserState, peer=None):
        try:
            self.user_manager.set_user_state(user_id, state, peer)
            logger.info(f"Updated User {user_id} state: {
                state} ({peer}).")
        except (UserNotFound, InvalidState) as e:
            logger.error(str(e))
            raise e

    def contact_client(self, user_id, route, json):
        endpoint = self.get_user(user_id).api_endpoint(route)
        logger.info(f"Contacting Client API for User {
            user_id} at {endpoint}.")
        try:
            response = requests.post(str(endpoint), json=json)
        except Exception as e:
            logger.error(f"Unable to reach Client API for User {
                user_id} at endpoint {endpoint}.")
            # TODO: Figure out specifically what exception is raised so I can catch only that, and then handle it instead of re-raising (or maybe re-raise different exception and then caller can handle)
            raise e
        return response

    def set_websocket_endpoint(self, endpoint):
        # if self.state >= ClientState.LIVE:
        #     raise InternalClientError("Cannot change Web Socket endpoint after connection already estbablished.") # TODO: use InvalidState

        self.websocket_endpoint = Endpoint(*endpoint)
        self.SocketAPI.endpoint = self.websocket_endpoint
        logger.info(f"Setting Web Socket endpoint: {
            self.websocket_endpoint}")

    def start_websocket(self, users):
        logger.info(f"Starting WebSocket API.")
        if not self.websocket_endpoint:
            raise ServerError(
                f"Cannot start WebSocket API without defined endpoint.")

        self.websocket_instance = self.SocketAPI.init(self, users)
        self.websocket_instance.start()

    def handle_peer_connection(self, user_id, peer_id):
        if user_id == peer_id:
            raise BadRequest(f"Cannot intermediate connection between User {
                             user_id} and self.")

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
            raise InvalidState(f"Cannot connect to peer User {
                               peer_id}: peer must be IDLE.")
        if user.state != UserState.IDLE:
            raise InvalidState(f"Cannot connect User {
                               user_id} to peer: User must be IDLE.")

        logger.info(f"Contacting User {
            peer_id} to connect to User {user_id}.")

        self.start_websocket(users=(user_id, peer_id))

        try:
            response = self.contact_client(peer_id, '/peer_connection', json={
                'peer_id': user_id,
                'socket_endpoint': tuple(self.websocket_endpoint)
            })
        except Exception as e:
            raise BadGateway(f"Unable to reach peer User {peer_id}.")

        if response.status_code != 200:
            logger.error(f"Peer User {peer_id} refused connection request.")
            raise BadGateway(
                f"Peer User {peer_id} refused connection request.")
        logger.info(f"Peer User {peer_id} accepted connection request.")
        return self.websocket_endpoint

# endregion


# region --- Main ---
if __name__ == "__main__":
    from api import ServerAPI
    # NOTE: This doesn't have the correct arguments now; not important, though
    server = Server(ServerAPI.DEFAULT_ENDPOINT)
# endregion
