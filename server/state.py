from functools import total_ordering
from enum import Enum


class APIState(Enum):
    INIT = 'INIT'
    IDLE = 'IDLE'
    LIVE = 'LIVE'


@total_ordering
class SocketState(Enum):
    NEW = 'NEW'
    INIT = 'INIT'
    LIVE = 'LIVE'
    OPEN = 'OPEN'

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented
