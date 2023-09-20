import socket
import threading
import logging
import hashlib
from user_manager import UserManager, UserStorageFactory
# from qber_manager import QBERManager

# Initialize logging
logging.basicConfig(filename='server.log', level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DuplicateUser(Exception):
    # for ex
    pass

class UserNotFound(Exception):
    # for ex
    pass

class Server:
    def __init__(self, host, port, user_storage="DICT"):
        self.host = host
        self.port = port
        with UserStorageFactory() as factory:
            storage = factory.create_storage(user_storage)
            self.user_manager = UserManager(storage=storage)
        self.qber_manager = None # QBERManager
        
    async def add_user(self, user_id, ip_address):
        try:
            self.user_manager.add_user(user_id, ip_address)
            logger.info(f"User {user_id} added successfully.")
        except DuplicateUser:
            logger.error("Duplicate user_id.")
            raise

    async def get_user(self, user_id):
        try:
            ip_address = self.user_manager.get_user(user_id)
            logger.info(f"Retrieved IP address {ip_address} for user {user_id}.")
            return ip_address
        except UserNotFound:
            logger.error("User not found.")
            raise

    async def remove_user(self, user_id):
        try:
            self.user_manager.remove_user(user_id)
            logger.info(f"User {user_id} removed successfully.")
        except UserNotFound:
            logger.error("User not found.")
            raise

if __name__ == "__main__":
    HOST = '127.0.0.1'
    PORT = 65431

    server = Server(host='localhost', port=5000)