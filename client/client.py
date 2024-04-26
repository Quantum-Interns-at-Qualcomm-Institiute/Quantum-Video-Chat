import tracemalloc

import time
import requests

#region --- Logging --- # TODO: Add internal logger to Client class
import logging
from utils.av import AV

# XXX: Switch back to level=logging.DEBUG
logging.basicConfig(filename='./client/logs/client.log', level=logging.INFO, 
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
#endregion


#region --- Utils ---
from utils import ClientState
from utils import get_parameters, is_type
from utils import ServerError, BadGateway, BadRequest, ParameterError, InvalidParameter, BadAuthentication, UserNotFound


class UnexpectedResponse(Exception):
    pass
class ConnectionRefused(UnexpectedResponse):
    pass
class InternalClientError(Exception):
    pass

from gui import Alert, Question
#endregion


#region --- Socket Client ---
from threading import Thread
import socketio
class SocketClient(): # Not threaded because sio.connect() is not blocking
    
    sio = socketio.Client()
    user_id = None
    endpoint = None
    conn_token = None
    sess_token = None
    instance = None
    namespaces = None
    av = None
    video = {}
    # state = SocketClientState.NEW
    # TODO: ^ there's a `client.connected` member variable; we can just use that tbh
    display_message = None

    #region --- Utils ---
    logger = logging.getLogger('SocketClient')

    @classmethod
    def set_sess_token(cls, sess_token):
        cls.logger.info(f"Setting session token '{sess_token}'")
        cls.sess_token = sess_token

    @classmethod
    def is_connected(cls):
        return cls.sio.connected

    def HandleExceptions(endpoint_handler):
        """
        Decorator to handle commonly encountered exceptions at Socket Client endpoints.
        
        NOTE: This should never be called explicitly
        """
        def handler_with_exceptions(*args, **kwargs):
            cls = SocketClient

            try: return endpoint_handler(cls, *args, **kwargs)
            except Exception as e: # TODO: Add excpetions
                raise e
        return handler_with_exceptions
    #endregion


    #region --- External Interface ---
    @classmethod
    def init(cls, endpoint, conn_token, user_id, display_message): # TODO: Unsure if client needed.
        cls.logger.info(f"Initiailizing Socket Client with WebSocket endpoint {endpoint}.")

        cls.av = AV(cls)
        cls.namespaces = cls.av.client_namespaces

        # if cls.state == SocketClientState.OPEN:
            # raise ServerError(f"Cannot reconfigure Socket Client while connection is open.")
        cls.conn_token = conn_token
        cls.endpoint = Endpoint(*endpoint)
        cls.user_id = user_id
        cls.display_message = display_message
        # cls.state = SocketClientState.INIT
        cls.instance = cls()
        return cls.instance
    
    def start(self):
        self.run()

    def run(self):
        SocketClient.connect()

    @classmethod
    def send_message(cls, msg: str, namespace='/'):
        # TODO: Ensure we're actually connected first lelz
        # cls.logger.info(f"Sending message: {msg}")
        cls.sio.send(((str(cls.user_id),cls.sess_token),msg), namespace=namespace)

    @classmethod
    def connect(cls):
        cls.logger.info(f"Attempting WebSocket connection to {cls.endpoint} with connection token '{cls.conn_token}'.")
        # TODO: State Management
        # cls.state = SocketClientState.OPEN
        try:
            ns = sorted(list(cls.namespaces.keys()))
            cls.sio.connect(str(cls.endpoint), wait_timeout=5, auth=(cls.user_id, cls.conn_token), namespaces=['/']+ns)
            for name in ns:
                cls.sio.register_namespace(cls.namespaces[name])
        except socketio.exceptions.ConnectionError as e:
            cls.logger.error(f"Connection failed: {str(e)}")

    @classmethod
    def disconnect(cls):
        # Check to make sure we're actually connected
        cls.logger.info(f"Disconnecting Socket Client from Websocket API.")
        cls.sio.disconnect()
        # Make sure to update state, delete instance if necessary, etc.

    @classmethod
    def kill(cls): 
        cls.logger.info(f"Killing Socket Client")
        cls.disconnect()
        # Make sure to update state, delete instance if necessary, etc.
    #endregion


    #region --- Event Endpoints ---
    @sio.on('connect')
    @HandleExceptions
    def on_connect(cls):
        # Set state
        # SocketClient.sess_token = sess_token
        cls.logger.info(f"Socket connection established to endpoint {SocketClient.endpoint}")
        ns = sorted(list(cls.namespaces.keys()))
        for name in ns:
            cls.namespaces[name].on_connect()

    @sio.on('token')
    @HandleExceptions
    def on_token(cls,sess_token):
        cls.logger.info(f"Received session token '{sess_token}'")
        SocketClient.set_sess_token(sess_token)

    @sio.on('message')
    @HandleExceptions
    def on_message(cls,user_id, msg):
        cls.logger.info(f"Received message from user {user_id}: {msg}")
        SocketClient.display_message(user_id, msg)

    #endregion
#endregion


#region --- Main Client ---
from utils import Endpoint
from api import ClientAPI
import cv2
class Client:
    def __init__(self, server_endpoint=None, api_endpoint=None, websocket_endpoint=None):
        self.logger = logging.getLogger('Client')
        self.logger.info(f"""Initializing Client with:
                         Server endpoint {server_endpoint},
                         Client API endpoint {api_endpoint},
                         WebSocket API endpoint {websocket_endpoint}.""")
        self.user_id = None
        self.sess_token = None
        self.state = ClientState.NEW

        self.server_endpoint = server_endpoint
        self.api_endpoint = api_endpoint
        self.websocket_endpoint = websocket_endpoint
        self.peer_endpoint = None
        self.api_instance = None
        self.websocket_instance = None

        self.gui = None

    #region --- Utils ---
    def authenticate_server(self, sess_token):
        return sess_token == self.sess_token

    # TODO: All endpoint functions should take a single endpoint obj.
    def set_server_endpoint(self, endpoint):
        if self.state >= ClientState.LIVE:
            raise InternalClientError("Cannot change server endpoint after connection already estbablished.") # TODO: use InvalidState

        self.server_endpoint = Endpoint(*endpoint)
        self.logger.info(f"Setting server endpoint: {self.server_endpoint}")

    def set_api_endpoint(self, endpoint):
        if self.state >= ClientState.LIVE:
            raise InternalClientError("Cannot change API endpoint after connection already estbablished.") # TODO: use InvalidState

        self.api_endpoint = Endpoint(*endpoint)
        ClientAPI.endpoint = self.api_endpoint
        self.logger.info(f"Setting API endpoint: {self.api_endpoint}")

    # def set_websocket_endpoint(self, endpoint):
    #     if self.state >= ClientState.LIVE:
    #         raise InternalClientError("Cannot change Web Socket endpoint after connection already estbablished.") # TODO: use InvalidState

    #     self.websocket_endpoint = Endpoint(*endpoint)
    #     SocketAPI.endpoint = self.websocket_endpoint
    #     self.logger.info(f"Setting Web Socket endpoint: {self.websocket_endpoint}")

    def display_message(self, user_id, msg):
        print(f"({user_id}): {msg}")

    def contact_server(self, route, json=None):
        endpoint = self.server_endpoint(route)
        self.logger.info(f"Contacting Server at {endpoint}.")

        try: response = requests.post(str(endpoint), json=json)
        except requests.exceptions.ConnectionError as e:
            raise ConnectionRefused(f"Unable to reach Server API at endpoint {endpoint}.")

        if response.status_code != 200:
            try: json = response.json()
            except requests.exceptions.JSONDecodeError as e:
                raise UnexpectedResponse(f"Unexpected Server response at {endpoint}: {response.reason}.")
            
            if 'details' in response.json():
                raise UnexpectedResponse(f"Unexpected Server response at {endpoint}: {response.json()['details']}.")
            raise UnexpectedResponse(f"Unexpected Server response at {endpoint}: {response.reason}.")
        return response

    def kill(self):
        try: ClientAPI.kill()
        except Exception: pass
        try: SocketClient.kill()
        except Exception: pass
        # try: SocketAPI.kill()
        # except Exception: pass
        try: requests.delete(str(self.server_endpoint('/remove_user')), json={
            'user_id': self.user_id,
            'sess_token': self.sess_token
        })
        except Exception: pass
        # Kill Socket Client
        # Kill Socket API
        # Kill Client API
        # Disconnect from server
        pass
    #endregion


    #region --- Server Interface ---
    # TODO: Client API should be LIVE first; need to give endpoint to server.
    def connect(self):
        """
        Attempt to connect to specified server. Expects token and user_id in return.
        Return `True` iff successful.
        """
        self.logger.info(f"Attempting to connect to server: {self.server_endpoint}.")
        if(self.state >= ClientState.LIVE):
            logger.error(f"Cannot connect to {self.server_endpoint}; already connected.")
            raise InternalClientError(f"Cannot connect to {self.server_endpoint}; already connected.")
    
        try:
            response = self.contact_server('/create_user', json={
                'api_endpoint': tuple(self.api_endpoint)
            })
        except ConnectionRefused as e:
            self.logger.error(str(e))
            return False
        except UnexpectedResponse as e:
            self.logger.error(str(e))
            raise e
        
        try:
            self.user_id, self.sess_token = get_parameters(response.json(), 'user_id', 'sess_token')
            self.logger.info(f"Received user_id '{self.user_id}' and token '{self.sess_token}'.")
        except ParameterError as e:
            self.logger.error(f"Server response did not contain both user_id and sess_token at {self.server_endpoint('/create_user')}.")
            raise UnexpectedResponse(f"Server response did not contain both user_id and sess_token at {self.server_endpoint('/create_user')}.")
        
        self.state = ClientState.LIVE
        print(f"Received user_id {self.user_id} and sess_token '{self.sess_token}'")
        return True
        

    def connect_to_peer(self, peer_id, frontend_socket):
        """
        Open Socket API. Contact Server /peer_connection with `conn_token` and await connection from peer (authenticated by `conn_token`).
        """
        self.logger.info(f"Attempting to initiate connection to peer User {peer_id}.")

        print(f"Requesting connection to {peer_id}")
        try:
            response = self.contact_server('/peer_connection', json={
                'user_id': self.user_id,
                'sess_token': self.sess_token,
                'peer_id': peer_id,
            })
        except ConnectionRefused as e:
            self.logger.error(str(e))
            raise e
        except UnexpectedResponse as e:
            self.logger.error(str(e))
            raise e

        websocket_endpoint, conn_token = get_parameters(response.json(), 'socket_endpoint', 'conn_token')      
        self.logger.info(f"Received websocket endpoint '{websocket_endpoint}' and conn_token '{conn_token}' from Server.")
        self.connect_to_websocket(websocket_endpoint, conn_token)
        while True:
            if SocketClient.is_connected(): break

    def disconnect_from_server(self):
        pass
    #endregion


    #region --- Client API Handlers ---
    def start_api(self):
        if not self.api_endpoint:
            raise InternalClientError(f"Cannot start Client API without defined endpoint.")

        self.api_instance = ClientAPI.init(self)
        self.api_instance.start()

    # TODO: Return case for failed connections
    def handle_peer_connection(self, peer_id, socket_endpoint, conn_token):
        """
        Initialize Socket Client and attempt connection to specified Socket API endpoint.
        Return `True` iff connection is successful

        Parameters
        ----------

        """
        if self.state == ClientState.CONNECTED:
            raise InternalClientError(f"Cannot attempt peer websocket connection while {self.state}.")   
    
        # self.logger.info("Polling User")
        # print(f"Incoming connection request from {peer_id}.")
        # ANDY_TODO: Remove the question
        # res = self.gui.question('Incoming Peer Connection', f"Peer User {peer_id} has requested to connect to you. Accept?")
        # if res == 'yes':
        # self.logger.info("User Accepted Connection.")
        self.logger.info(f"Attempting to connect to peer {peer_id} at {socket_endpoint} with token '{conn_token}'.")

        try:
            self.connect_to_websocket(socket_endpoint, conn_token)
        except Exception as e:
            self.gui.alert('Warning', f"Connection to incoming peer User {peer_id} failed.")
            return False
        self.logger.info(f"Successfully connected to peer User {peer_id}.")
        # XXX: WHY THE FUCK IS THIS BLOCKING????
        self.gui.quit('User accepted an incoming connection request.')
        self.logger.info(f"Just quit da GUI; returning from client.handle_peer_connection().")
        return True
        # else:
        #     self.logger.info("User Refused Connection.")
        #     return False
        # return False
        
    def disconnect_from_peer(self):
        pass
    #endregion


    #region --- Web Socket Interface ---
    # def start_websocket(self, users):
    #     if not self.websocket_endpoint:
    #         raise InternalClientError(f"Cannot start WebSocket API without defined endpoint.")

    #     self.websocket_instance = SocketAPI.init(self, users)
    #     self.websocket_instance.start()


    def connect_to_websocket(self, endpoint, conn_token):
        sio = SocketClient.init(endpoint, conn_token, self.user_id, self.display_message)
        try:
            sio.start()
        except Exception as e:
            self.logger.error(f"Failed to connect to WebSocket at {endpoint} with conn_token '{conn_token}'.")
            raise e
    #endregion
#endregion


#region --- Main ---
from gui import InitClientGUI, MainGUI
from gui import GUIQuit

if __name__ == "__main__":
    client = Client(api_endpoint=ClientAPI.DEFAULT_ENDPOINT)
    client.start_api()
    currGUI = None
    alert = None
    question = None

    try:
        while client.state < ClientState.LIVE:
            currGUI = InitClientGUI()
            if alert:
                alert.show()
                alert = None
            currGUI.run()

            server_endpoint = Endpoint(*currGUI.server_endpoint)
            try:
                client.set_server_endpoint(server_endpoint)
                client.connect() 
            except UnexpectedResponse as e:
                alert = alert('Warning', str(e), lambda x: print('hi'))

            if client.state < ClientState.LIVE:
                alert = Alert('Warning', f"Unable to reach endpoint {server_endpoint}")
                continue
            else: break


        #region --- Main GUI ---
        alert = None
        while True:
            mainGUI = currGUI = MainGUI(client.user_id)
            client.gui = currGUI
            if alert: 
                alert.show()
                alert = None
            
            try:
                mainGUI.run()
            except GUIQuit as e:
                if str(e) == 'User accepted an incoming connection request.': break
                raise e

            peer_id = mainGUI.peer_id
            try:
                client.connect_to_peer(peer_id)
            except UnexpectedResponse as e:
                alert = Alert('Warning', str(e).split(": ")[-1])
                SocketClient.kill()
                continue

            if client.state < ClientState.CONNECTED:
                alert = Alert('Warning', f"Failed to connect to User {peer_id}")
                continue
            else: break

        #endregion


        #region --- Chat GUI ---
        while True:
            if SocketClient.is_connected(): break

        SocketClient.send_message(f"Hello from user {client.user_id}")
        input("Press Enter to continue...")
        tracemalloc.start()
        while True:
            # msg = input()
            # print([SocketClient.av.key_queue[user_id]['/video_key'].qsize() for user_id in SocketClient.av.key_queue])
            # if '/test' in SocketClient.namespaces:
            #     SocketClient.send_message(msg, namespace='/test')
            # else:
            #     SocketClient.send_message(msg)

            # this is here in the main thread because cv2 only runs in the main thread for macOS
            for user_id in SocketClient.video:
                window_name = f"User {user_id}" if user_id != client.user_id else "Self"

                # my computer can't handle 4 displays at once so I'm not gonna show the self display
                # if window_name == "Self": continue

                cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(window_name, SocketClient.av.display_shape[1], SocketClient.av.display_shape[0])
                cv2.imshow(window_name, SocketClient.video[user_id])
                cv2.waitKey(1)
            print("mem", tracemalloc.get_traced_memory())
            time.sleep(1/SocketClient.av.frame_rate)
        #endregion

    except GUIQuit as e:
        logger.info(f"{str(e)}\n")
        client.kill()
        exit()
    except KeyboardInterrupt as e:
        logger.info("Keyboard Interrupt.\n")
        client.kill()
        exit()
        # TODO: Other stuff; eg: kill api server, etc.
        # if currGUI: currGUI.kill()
        # logger.info("Exiting main program execution.\n")
    except Exception as e:
        logger.error(f"Encountered unexpected exception: {str(e)}\n")
        raise e
    # logger.info("Reached end of execution.\n")
#endregion