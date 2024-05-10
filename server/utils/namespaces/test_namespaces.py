import asyncio
import logging
from flask_socketio import send
from flask_socketio.namespace import Namespace as FlaskNamespace
from socketio import ClientNamespace

from utils import ClientState
logging.basicConfig(filename='./logs/server.log', level=logging.DEBUG,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')


def display_message(user_id, msg):
    print(f"({user_id}): {msg}")


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
        # self.cls.logger.info(f"Client disconnected from namespace {self.namespace}.")
        # TODO: use client.set_state()
        if self.cls.client.state == ClientState.CONNECTED:
            self.cls.client.state = ClientState.LIVE


class TestClientNamespace(ClientNamespace):

    def __init__(self, namespace, cls, *kwargs):
        super().__init__(namespace)
        self.cls = cls

    def on_connect(self):
        # self.cls.logger.info(f"Socket connection established to endpoint {self.cls.endpoint} on namespace /test")
        display_message(self.cls.user_id, "Connected to /test")

    def on_message(self, user_id, msg):
        msg = '/test: ' + msg
        # self.cls.logger.info(f"Received /test message from user {user_id}: {msg}")

        async def disp():
            display_message(user_id, msg)
        asyncio.run(disp())
