"""User storage, management, and lifecycle for the QKD server."""

# from __future__ import annotations

# region --- Logging ---
import secrets
import threading
from abc import ABC, abstractmethod

from custom_logging import logger

from shared.exceptions import InvalidState

from .user import User, UserState

# endregion

# User ID generation bounds
_MIN_USER_ID = 10000
_MAX_USER_ID = 99999
_FALLBACK_MIN_USER_ID = 100000
_FALLBACK_MAX_USER_ID = 999999


# region --- Utils ---


class DuplicateUserError(Exception):
    """Raised when attempting to add a user that already exists."""


# Keep old name as alias for backward compatibility
DuplicateUser = DuplicateUserError


class UserNotFoundError(Exception):
    """Raised when a requested user does not exist."""


# Keep old name as alias for backward compatibility
UserNotFound = UserNotFoundError

# endregion


# region --- Storage ---


class UserStorageInterface(ABC):
    """Abstract interface for user storage backends."""

    @abstractmethod
    def add_user(self, user_id, user_info):
        """Add a user to storage."""

    @abstractmethod
    def update_user(self, user_id, user_info):
        """Update an existing user's info."""

    @abstractmethod
    def get_user(self, user_id):
        """Retrieve a user by ID."""

    @abstractmethod
    def remove_user(self, user_id):
        """Remove a user from storage."""

    @abstractmethod
    def has_user(self, user_id):
        """Return whether a user exists."""

    @abstractmethod
    def get_all_users(self):
        """Return all users."""


class DictUserStorage(UserStorageInterface):
    """In-memory dict-based user storage with thread safety."""

    def __init__(self):
        """Initialize empty user store with lock."""
        self.users = {}
        self._lock = threading.Lock()

    def add_user(self, user_id, user_info):
        """Add a user, raising DuplicateUserError if already present."""
        with self._lock:
            if user_id in self.users:
                msg = f"Cannot add user {user_id}: User already exists."
                raise DuplicateUserError(msg)
            self.users[user_id] = user_info

    def update_user(self, user_id, user_info):
        """Update user info, raising UserNotFoundError if missing."""
        with self._lock:
            if user_id not in self.users:
                msg = f"Cannot update user {user_id}: User does not exist."
                raise UserNotFoundError(msg)
            self.users[user_id] = user_info

    def get_user(self, user_id):
        """Retrieve a user by ID, raising UserNotFoundError if missing."""
        with self._lock:
            if user_id not in self.users:
                msg = f"Cannot get user {user_id}: User does not exist."
                raise UserNotFoundError(msg)
            return self.users.get(user_id, None)

    def remove_user(self, user_id):
        """Remove a user by ID, raising UserNotFoundError if missing."""
        with self._lock:
            if user_id not in self.users:
                msg = f"Cannot remove user {user_id}: User does not exist."
                raise UserNotFoundError(msg)
            del self.users[user_id]

    def has_user(self, user_id):
        """Return whether the user exists in storage."""
        with self._lock:
            return user_id in self.users

    def get_all_users(self):
        """Return a shallow copy of all users."""
        with self._lock:
            return dict(self.users)


class UserStorageFactory:
    """Factory for creating user storage backends."""

    def __init__(self):
        """Initialize the factory."""

    def __enter__(self):
        """Return self as context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up context manager resources."""

    def create_storage(self, storage_type: str, **_kwargs) -> UserStorageInterface:
        """Create a storage backend by type name."""
        if storage_type == "DICT":
            return DictUserStorage()
        msg = f"Invalid storage type: {storage_type}"
        raise ValueError(msg)
# endregion


# region --- User Manager ---


class UserManager:
    """High-level user management operations over a storage backend."""

    def __init__(self, storage: UserStorageInterface):
        """Initialize with a user storage backend."""
        self.storage = storage
        logger.debug("UserManager initialized with %s", type(storage).__name__)

    def generate_user_id(self):
        """Generate a unique 5-digit numeric user ID (10000-99999)."""
        for _ in range(100):  # avoid infinite loop on a very full server
            user_id = str(secrets.randbelow(_MAX_USER_ID - _MIN_USER_ID + 1) + _MIN_USER_ID)
            if not self.storage.has_user(user_id):
                return user_id
        # Fallback: expand to 6 digits if 5-digit space is exhausted
        return str(secrets.randbelow(_FALLBACK_MAX_USER_ID - _FALLBACK_MIN_USER_ID + 1) + _FALLBACK_MIN_USER_ID)

    def add_user(self, api_endpoint):
        """Create a new user with a generated ID and return the ID."""
        user_id = self.generate_user_id()
        try:
            self.storage.add_user(user_id, User(api_endpoint))
            logger.debug("Added User %s.", user_id)
        except DuplicateUserError as e:
            logger.error(str(e))
            raise
        else:
            return user_id

    def set_user_state(self, user_id, state: UserState, peer=None):
        """Update a user's state and optional peer reference."""
        if (state == UserState.IDLE) ^ (peer is None):
            msg = f"Cannot set state {state} ({peer}) for User {user_id}: Invalid state."
            raise InvalidState(msg)

        try:
            user_info = self.storage.get_user(user_id)
            user_info.state = state
            user_info.peer = peer
            self.storage.update_user(user_id, user_info)
            logger.debug("Updated User %s state: %s (%s).", user_id, state, peer)
        except UserNotFoundError as e:
            logger.error(str(e))
            raise

    def get_user(self, user_id) -> User:
        """Retrieve a user by ID."""
        try:
            user_info = self.storage.get_user(user_id)
            logger.debug("Retrieved user info for User %s.", user_id)
        except UserNotFoundError as e:
            logger.error(str(e))
            raise
        else:
            return User(*user_info)

    def remove_user(self, user_id):
        """Remove a user from storage."""
        try:
            self.storage.remove_user(user_id)
            logger.debug("Removed User %s.", user_id)
        except UserNotFoundError as e:
            logger.error(str(e))

    def get_all_users(self):
        """Return all users as a dict of serialized info."""
        users = self.storage.get_all_users()
        return {
            uid: {
                "api_endpoint": str(user.api_endpoint),
                "state": user.state.value,
                "peer": user.peer,
            }
            for uid, user in users.items()
        }
# endregion
