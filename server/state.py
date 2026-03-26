"""Server state enums for API and socket lifecycle."""

from enum import Enum
from functools import total_ordering


class APIState(Enum):
    """REST API lifecycle states."""
    INIT = "INIT"
    IDLE = "IDLE"
    LIVE = "LIVE"


@total_ordering
class SocketState(Enum):
    """WebSocket lifecycle states with ordering support."""
    NEW = "NEW"
    INIT = "INIT"
    LIVE = "LIVE"
    OPEN = "OPEN"

    def __lt__(self, other):
        """Return whether this state precedes the other in lifecycle order."""
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented
