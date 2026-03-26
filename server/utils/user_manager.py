# from __future__ import annotations

# region --- Logging ---
import random
import threading
from abc import ABC, abstractmethod

from custom_logging import logger

from shared.exceptions import InvalidState

from .user import User, UserState

# endregion


# region --- Utils ---


class DuplicateUser(Exception):
    pass


class UserNotFound(Exception):
    pass

# endregion


# region --- Storage ---


class UserStorageInterface(ABC):

    @abstractmethod
    def add_user(self, user_id, user_info):
        pass

    @abstractmethod
    def update_user(self, user_id, user_info):
        pass

    @abstractmethod
    def get_user(self, user_id):
        pass

    @abstractmethod
    def remove_user(self, user_id):
        pass

    @abstractmethod
    def has_user(self, user_id):
        pass

    @abstractmethod
    def get_all_users(self):
        pass


class DictUserStorage(UserStorageInterface):

    def __init__(self):
        self.users = {}
        self._lock = threading.Lock()

    def add_user(self, user_id, user_info):
        with self._lock:
            if user_id in self.users:
                raise DuplicateUser(f"Cannot add user {user_id}: User already exists.")
            self.users[user_id] = user_info

    def update_user(self, user_id, user_info):
        with self._lock:
            if user_id not in self.users:
                raise UserNotFound(f"Cannot update user {user_id}: User does not exist.")
            self.users[user_id] = user_info

    def get_user(self, user_id):
        with self._lock:
            if user_id not in self.users:
                raise UserNotFound(f"Cannot get user {user_id}: User does not exist.")
            return self.users.get(user_id, None)

    def remove_user(self, user_id):
        with self._lock:
            if user_id not in self.users:
                raise UserNotFound(f"Cannot remove user {user_id}: User does not exist.")
            del self.users[user_id]

    def has_user(self, user_id):
        with self._lock:
            return user_id in self.users

    def get_all_users(self):
        with self._lock:
            return dict(self.users)


class UserStorageFactory:
    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def create_storage(self, storage_type: str, **kwargs) -> UserStorageInterface:
        if storage_type == 'DICT':
            return DictUserStorage()
        else:
            raise ValueError(f"Invalid storage type: {storage_type}")
# endregion


# region --- User Manager ---


class UserManager:

    def __init__(self, storage: UserStorageInterface):
        self.storage = storage

    def generate_user_id(self):
        """Generate a unique 5-digit numeric user ID (10000–99999)."""
        for _ in range(100):  # avoid infinite loop on a very full server
            user_id = str(random.randint(10000, 99999))
            if not self.storage.has_user(user_id):
                return user_id
        # Fallback: expand to 6 digits if 5-digit space is exhausted
        return str(random.randint(100000, 999999))

    def add_user(self, api_endpoint):
        user_id = self.generate_user_id()
        try:
            self.storage.add_user(user_id, User(api_endpoint))
            logger.debug(f"Added User {user_id}'.")
            return user_id
        except DuplicateUser as e:
            logger.error(str(e))
            raise e

    def set_user_state(self, user_id, state: UserState, peer=None):
        if (state == UserState.IDLE) ^ (peer is None):
            raise InvalidState(f"Cannot set state {state} ({peer}) for User {user_id}: Invalid state.")

        try:
            user_info = self.storage.get_user(user_id)
            user_info.state = state
            user_info.peer = peer
            self.storage.update_user(user_id, user_info)
            logger.debug(f"Updated User {user_id} state: {state} ({peer}).")
        except UserNotFound as e:
            logger.error(str(e))
            raise e

    def get_user(self, user_id) -> User:
        try:
            user_info = self.storage.get_user(user_id)
            logger.debug(f"Retrieved user info for User {user_id}.")
            return User(*user_info)
        except UserNotFound as e:
            logger.error(str(e))
            raise e

    def remove_user(self, user_id):
        try:
            self.storage.remove_user(user_id)
            logger.debug(f"Removed User {user_id}.")
        except UserNotFound as e:
            logger.error(str(e))

    def get_all_users(self):
        users = self.storage.get_all_users()
        return {
            uid: {
                'api_endpoint': str(user.api_endpoint),
                'state': user.state.value,
                'peer': user.peer,
            }
            for uid, user in users.items()
        }
# endregion
