import asyncio
import logging
from flask_socketio.namespace import Namespace as FlaskNamespace
from socketio import ClientNamespace
from flask_socketio import send
from client.util import ClientState, display_message

logging.basicConfig(filename='./src/middleware/logs/client.log',
                    level=logging.INFO,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')


class TestFlaskNamespace(FlaskNamespace):
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

        send((user_id, msg), broadcast=True)

    def on_disconnect(self):
        # TODO: use client.set_state()
        if self.cls.client.state == ClientState.CONNECTED:
            self.cls.client.state = ClientState.LIVE


class TestClientNamespace(ClientNamespace):

    def __init__(self, namespace, cls, *kwargs):
        super().__init__(namespace)
        self.cls = cls

    def on_connect(self):
        display_message(self.cls.user_id, "Connected to /test")

    def on_message(self, user_id, msg):
        msg = '/test: ' + msg

        async def disp():
            display_message(user_id, msg)
        asyncio.run(disp())
