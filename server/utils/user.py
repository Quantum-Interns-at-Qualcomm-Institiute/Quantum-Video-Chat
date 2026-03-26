"""User model and state enum for the QKD server."""

from enum import Enum

from . import Endpoint


class UserState(Enum):
    """Connection states for a server-managed user."""
    IDLE = "IDLE"
    AWAITING_CONNECTION = "AWAITING CONNECTION"
    CONNECTED = "CONNECTED"


class User:
    """Represents a connected user with endpoint, state, and peer info."""

    def __init__(self, api_endpoint: Endpoint, state=UserState.IDLE, peer=None):
        """Initialize a user with endpoint, state, and optional peer."""
        self.api_endpoint = Endpoint(*api_endpoint)
        self.state = state
        self.peer = peer

    def __iter__(self):
        """Yield endpoint, state, and peer."""
        yield self.api_endpoint
        yield self.state
        yield self.peer

    def __str__(self):
        """Return string representation."""
        return str(tuple(self))
