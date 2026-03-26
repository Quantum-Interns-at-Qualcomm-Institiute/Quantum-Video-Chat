"""Server-specific exception types."""

from shared.exceptions import InvalidStateError  # noqa: F401 -- re-export


class IdentityMismatchError(Exception):
    """Raised when a user's identity does not match the expected value."""
