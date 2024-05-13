from flask_socketio import send
from socketio import Client as SocketIOClient, ClientNamespace
from flask_socketio.namespace import Namespace as FlaskNamespace
from client.util import ClientState


class BroadcastFlaskNamespace(FlaskNamespace):
    def __init__(self, namespace, client_socket):
        super().__init__(namespace=namespace)
        self.client_socket = client_socket
        self.namespace = namespace

    def on_connect(self):
        pass

    def on_message(self, auth, msg):
        user_id, sess_token = auth
        user_id = user_id
        if not self.client_socket.verify_sess_token(*auth):
            return

        send((user_id, msg), broadcast=True, include_self=False)

    def on_disconnect(self):
        # TODO: use client.set_state
        if self.client_socket.client.state == ClientState.CONNECTED:
            self.client_socket.client.state = ClientState.LIVE


class AVClientNamespace(ClientNamespace):

    def __init__(self, namespace, client_socket, av_controller,
                 frontend_socket: SocketIOClient):
        super().__init__(namespace=namespace)
        self.client_socket = client_socket
        self.av_controller = av_controller
        self.frontend_socket: SocketIOClient = frontend_socket
        print("created AVClientNamespace", self.client_socket, self.av_controller)

    def on_connect(self):
        pass

    def on_message(self, user_id, msg):
        pass

    def send(self, msg):
        self.client_socket.send_message(msg, namespace=self.namespace)
