from . import Endpoint
from enum import Enum


class UserState(Enum):
    IDLE = 'IDLE'
    AWAITING_CONNECTION = 'AWAITING CONNECTION'
    CONNECTED = 'CONNECTED'


class User:
    def __init__(self, api_endpoint: Endpoint, state=UserState.IDLE, peer=None):
        self.api_endpoint = Endpoint(*api_endpoint)
        self.state = state
        self.peer = peer

    def __iter__(self):
        yield self.api_endpoint
        yield self.state
        yield self.peer

    def __str__(self):
        return str(tuple(self))
