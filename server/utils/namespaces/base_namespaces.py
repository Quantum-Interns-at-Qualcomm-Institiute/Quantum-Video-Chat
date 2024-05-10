from flask_socketio import send
from flask_socketio.namespace import Namespace as FlaskNamespace
from socketio import ClientNamespace
from utils import ClientState


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

        # Change include_self to True if you want your own video to be displayed
        send((user_id, msg), broadcast=True, include_self=False)

    def on_disconnect(self):
        # TODO: these lines are erroring
        if self.cls.client.state == ClientState.CONNECTED:
            self.cls.client.state = ClientState.LIVE


class AVClientNamespace(ClientNamespace):

    def __init__(self, namespace, cls, av):
        super().__init__(namespace)
        self.cls = cls
        self.av = av  # No type safety since that creates circular dependency
        print("created AVClientNamespace", self.cls, self.av)

    def on_connect(self):
        print("on_connect")

    def on_message(self, user_id, msg):
        pass

    def send(self, msg):
        self.cls.send_message(msg, namespace=self.namespace)
