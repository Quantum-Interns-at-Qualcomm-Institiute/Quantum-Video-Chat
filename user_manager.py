import hashlib
import logging
from abc import ABC, abstractmethod

# Initialize logging
logging.basicConfig(filename='user_manager.log', level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UserStorageInterface(ABC):

    @abstractmethod
    def add_user(self, user_id, user_info):
        pass

    @abstractmethod
    def get_user(self, user_id):
        pass

    @abstractmethod
    def remove_user(self, user_id):
        pass

class DictUserStorage(UserStorageInterface):

    def __init__(self):
        self.users = {}

    def add_user(self, user_id, user_info):
        if user_id in self.users:
            raise DuplicateUser(f"User ID {user_id} already exists.")
        self.users[user_id] = user_info

    def get_user(self, user_id):
        return self.users.get(user_id, None)

    def remove_user(self, user_id):
        if user_id in self.users:
            del self.users[user_id]

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

class DuplicateUser(Exception):
    pass

class UserNotFound(Exception):
    pass

class UserManager:


    def remove_user(self, user_id):
        if user_id not in self.users:
            logger.error(f"User {user_id} not found.")
            raise UserNotFound(f"User ID {user_id} does not exist.")
        del self.users[user_id]
        logger.info(f"Removed user {user_id}.")

class UserManager:

    def __init__(self, storage: UserStorageInterface):
        self.storage = storage

    def generate_user_id(self, ip_address, port):
        hash_object = hashlib.sha256(f"{ip_address}{port}".encode())
        user_id = hash_object.hexdigest()[:5]
        return user_id

    def add_user(self, ip_address, port):
        user_id = self.generate_user_id(ip_address, port)
        user_info = {'ip_address': ip_address, 'port': port}
        try:
            self.storage.add_user(user_id, user_info)
            logger.info(f"Added user {user_id} with IP address {ip_address} and port {port}.")
            return user_id
        except DuplicateUser as e:
            logger.error(f"Duplicate user_id: {user_id}")
            raise e

    def get_user(self, user_id):
        user_info = self.storage.get_user(user_id)
        if user_info is None:
            logger.error(f"User {user_id} not found.")
            raise UserNotFound(f"User ID {user_id} does not exist.")
        logger.info(f"Retrieved user info for user {user_id}.")
        return user_info

    def remove_user(self, user_id):
        self.storage.remove_user(user_id)
        logger.info(f"Removed user {user_id}.")
