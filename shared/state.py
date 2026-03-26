"""Client state enum for middleware lifecycle tracking."""

from enum import Enum
from functools import total_ordering


@total_ordering
class ClientState(Enum):
    """Client lifecycle states with ordering support."""
    NEW = "NEW"         # Uninitialized
    INIT = "INIT"       # Initialized
    LIVE = "LIVE"       # Connected to server
    CONNECTED = "CONNECTED"  # Connected to peer

    def __lt__(self, other):
        """Return whether this state precedes the other in lifecycle order."""
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented
