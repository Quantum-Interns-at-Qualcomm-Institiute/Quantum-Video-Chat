from flask_socketio import send
from socketio import Client as SocketIOClient, ClientNamespace
from flask_socketio.namespace import Namespace as FlaskNamespace
from client.util import ClientState


class BroadcastFlaskNamespace(FlaskNamespace):
    def __init__(self, namespace, cls):
        super().__init__(namespace)
        self.cls = cls
        self.namespace = namespace

    def on_connect(self):
        pass

    def on_message(self, auth, msg):
        user_id, sess_token = auth
        user_id = user_id
        if not self.cls.verify_sess_token(*auth):
            return

        send((user_id, msg), broadcast=True, include_self=False)

    def on_disconnect(self):
        # TODO: use client.set_state
        if self.cls.client.state == ClientState.CONNECTED:
            self.cls.client.state = ClientState.LIVE


class AVClientNamespace(ClientNamespace):

    def __init__(self, namespace, cls: type, av,
                 frontend_socket: SocketIOClient):
        super().__init__(namespace)
        self.cls: type = cls
        self.av = av
        self.frontend_socket: SocketIOClient = frontend_socket
        print("created AVClientNamespace", self.cls, self.av)

    def on_connect(self):
        pass

    def on_message(self, user_id, msg):
        pass

    def send(self, msg):
        self.cls.send_message(msg, namespace=self.namespace)
