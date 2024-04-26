from enum import Enum
class UserState(Enum):
    IDLE = 'IDLE'
    AWAITING_CONNECTION = 'AWAITING CONNECTION'
    CONNECTED = 'CONNECTED'

from . import Endpoint
class User:
    def __init__(self, api_endpoint: Endpoint, sess_token: str, state=UserState.IDLE, peer=None):
        self.api_endpoint = Endpoint(*api_endpoint)
        self.sess_token = sess_token
        self.state = state
        self.peer = peer

    def __iter__(self):
        yield self.api_endpoint
        yield self.sess_token
        yield self.state
        yield self.peer

    def __str__(self):
        return str(tuple(self))