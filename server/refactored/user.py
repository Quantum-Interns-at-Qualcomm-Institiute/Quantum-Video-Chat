import logging
from abc import ABC, abstractmethod
from enum import Enum
from hashlib import sha256
from typing import Optional

from server_exceptions import ServerExceptions
from states import UserState
from utils import Endpoint


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


class UserStorageInterface(ABC):
    @abstractmethod
    def __str__(self):
        pass

    @abstractmethod
    def add_user(self, user_id, user_info):
        pass

    @abstractmethod
    def update_user(self, user_id, user_info):
        pass

    @abstractmethod
    def get_user_by_id(self, user_id):
        pass

    @abstractmethod
    def remove_user(self, user_id):
        pass

    @abstractmethod
    def has_user(self, user_id):
        pass


class DictUserStorage(UserStorageInterface):

    def __init__(self):
        self.users = {}

    def __str__(self):
        return "Dictionary"

    def add_user(self, user_id, user_info: User):
        if user_id in self.users:
            raise ServerExceptions.DUPLICATE_USER(f"Cannot add user {user_id}: User already exists.")
        self.users[user_id] = user_info

    def update_user(self, user_id, user_info):
        if user_id not in self.users:
            raise ServerExceptions.USER_NOT_FOUND(f"Cannot update user {user_id}: User does not exist.")
        self.users[user_id] = user_info

    def get_user_by_id(self, user_id):
        if user_id not in self.users:
            raise ServerExceptions.USER_NOT_FOUND(f"Cannot get user {user_id}: User does not exist.")
        return self.users.get(user_id, None)

    def remove_user(self, user_id):
        if user_id not in self.users:
            raise ServerExceptions.USER_NOT_FOUND(f"Cannot remove user {user_id}: User does not exist.")
        del self.users[user_id]

    def has_user(self, user_id):
        return user_id in self.users


class UserStorageTypes(Enum):
    DICT = DictUserStorage

    def __call__(cls):
        return cls.value()


class UserStorageFactory:
    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def create_storage(self, storage_type: str, **kwargs) -> UserStorageInterface:
        if storage_type in UserStorageTypes:
            return storage_type()
        else:
            raise ValueError(f"Invalid storage type: {storage_type}")


class UserManager:

    def __init__(self, storage: UserStorageInterface):
        self.storage = storage
        self.logger = logging.getLogger("UserManager")

    # I would personally just generate a completely random string every time, but#
    # we do this in Andy's interest of having perfect reproducibility during testing
    def generate_user_id(self, endpoint: str):
        self.logger.debug(
            f"Generating User ID for user with API Endpoint {endpoint}.")
        hash_object = sha256(endpoint.encode())
        user_id = hash_object.hexdigest()[:5]

        hash_object = sha256(hash_object.hexdigest().encode())
        user_id = hash_object.hexdigest()[:5]
        shift = 0

        while self.storage.has_user(user_id):
            shift += 1
            user_id = hash_object.hexdigest()[shift: 5 + shift]

        return user_id

    # See note for generate_user_id(); the particular choice of seed here is a bit AIDS, though.
    # Also note uniqueness is not strictly necessary for tokens, so I've omitted it.
    def generate_token(self, user_id):
        self.logger.debug(f"Generating token for User {user_id}.")
        hash_object = sha256(user_id.encode())
        token = hash_object.hexdigest()

        return token

    def add_user(self, endpoint: Endpoint):
        user_id = self.generate_user_id(str(endpoint))
        sess_token = self.generate_token(user_id)
        user = User(user_id, sess_token, endpoint)
        try:
            self.storage.add_user(user_id, user)
            self.logger.debug(
                f"Added User {user_id} with session token '{sess_token}'.")
            return user_id, sess_token
        except ServerExceptions.DUPLICATE_USER as e:
            self.logger.error(str(e))
            raise e

    def set_user_state(self, user_id, state: UserState, peer=None):
        if (state == UserState.IDLE) ^ (peer is None):
            raise ServerExceptions.INVALID_STATE(f"Cannot set state {state} ({peer}) for User {user_id}: Invalid state.")

        try:
            user_info = self.storage.get_user_by_id(user_id)
            user_info.state = state
            user_info.peer = peer
            self.storage.update_user(user_id, user_info)
            self.logger.debug(f"Updated User {user_id} state: {state} ({peer}).")
        except ServerExceptions.USER_NOT_FOUND as e:
            self.logger.error(str(e))
            raise e

    def get_user_by_id(self, user_id) -> User:
        try:
            user_info = self.storage.get_user_by_id(user_id)
            self.logger.debug(f"Retrieved user info for User {user_id}.")
            return User(*user_info)
        except ServerExceptions.USER_NOT_FOUND as e:
            self.logger.error(str(e))
            raise e

    def remove_user(self, user_id):
        try:
            self.storage.remove_user(user_id)
            self.logger.debug(f"Removed User {user_id}.")
        except ServerExceptions.USER_NOT_FOUND as e:
            self.logger.error(str(e))
