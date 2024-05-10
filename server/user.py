from typing import Optional
from utils import Endpoint
from enum import Enum


class UserState(Enum):
    IDLE = 'IDLE'
    AWAITING_CONNECTION = 'AWAITING CONNECTION'
    CONNECTED = 'CONNECTED'


class User:
    def __init__(self, id: str, sess_token: str, api_endpoint: Endpoint, state: Optional[UserState] = None):
        self.id: str = id
        self.sess_token: str = sess_token
        self.api_endpoint: Endpoint = Endpoint(*api_endpoint)
        self.state: UserState = UserState.IDLE
        # self.peer: User = None

    def set_state(self, state: UserState):
        # TODO: checks
        self.state = state

    # def set_peer(self, peer: 'User'):
    #     self.peer = peer

    def __iter__(self):
        yield self.id
        yield self.sess_token
        yield self.api_endpoint
        yield self.state
        # yield self.peer

    def __str__(self):
        return str(tuple(self))
