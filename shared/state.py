from enum import Enum
from functools import total_ordering


@total_ordering
class ClientState(Enum):
    NEW = 'NEW'         # Uninitialized
    INIT = 'INIT'       # Initialized
    LIVE = 'LIVE'       # Connected to server
    CONNECTED = 'CONNECTED'  # Connected to peer

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented
