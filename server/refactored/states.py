from enum import Enum
from functools import total_ordering


@total_ordering
class ClientState(Enum):
    NEW = 'NEW'  # Uninitialized
    INIT = 'INIT'  # Initialized
    LIVE = 'LIVE'  # Connected to server
    CONNECTED = 'CONNECTED'  # Connected to peer

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented


@total_ordering
class ServerState(Enum):
    NEW = 'NEW'
    INITIALIZED = 'INITIALIZED'
    CLOSED = 'CLOSED'
    LIVE = 'LIVE'
    OPEN = 'OPEN'

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented


class APIState(Enum):
    INIT = 'INIT'
    IDLE = 'IDLE'
    LIVE = 'LIVE'


class UserState(Enum):
    IDLE = 'IDLE'
    AWAITING_CONNECTION = 'AWAITING CONNECTION'
    CONNECTED = 'CONNECTED'
