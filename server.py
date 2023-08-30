# Importing required libraries
import socket
import threading
import logging
import hashlib

class UserIDManager:
    def __init__(self):
        self.client_ids = {}

    def id_exists(self, user_id):
        return user_id in self.client_ids

    def generate_id(self, addr):
        addr_str = f"{addr[0]}:{addr[1]}"
        return hashlib.sha1(addr_str.encode()).hexdigest()[:5]

    def add_id(self, unique_id, addr):
        self.client_ids[unique_id] = addr

    def get_addr(self, query_id):
        return self.client_ids.get(query_id, None)
    
    def del_id(self, user_id):
        if self.id_exists(user_id):
            del self.client_ids[user_id]


class ClientHandler(threading.Thread):
    def __init__(self, conn, addr, user_id_manager):
        super().__init__()
        self.conn = conn
        self.addr = addr
        self.user_id_manager = user_id_manager
        self.user_id = None

    def run(self):
        try:
            self.handle()
        except Exception as e:
            logging.error(f"Exception while handling client {self.addr}: {str(e)}", exc_info=True)
        finally:
            self.conn.close()
            if self.user_id:
                self.user_id_manager.del_id(self.user_id)
            logging.info(f"Connection closed with {self.addr}")

    def handle(self):
        self.user_id = self.user_id_manager.generate_id(self.addr)
        self.user_id_manager.add_id(self.user_id, self.addr)
        logging.info(f"Assigned ID {self.user_id} to {self.addr}")
        self.conn.sendall(f"Your ID is {self.user_id}".encode())
        while True:
            command = self.conn.recv(1024).decode()
            if not command:
                logging.info(f"Connection terminated by client {self.addr}")
                break
            self.process_command(command)

    def process_command(self, command):
        handlers = {
            '1': self.check_id_existence,
            '2': self.ping,
            '3': self.connect_to_client,
            '4': self.toggle_client_listen
        }
        handler = handlers.get(command)
        if handler:
            handler()
        else:
            logging.warning(f"Unknown command {command} from client {self.user_id}{self.addr}")

    def toggle_client_listen(self):
        logging.info(f"Toggle client listen command received. Current server port: {self.addr[1]}")

    def connect_to_client(self):
        logging.info(f"Connect to client command received from {self.addr}")
        
        query_id = self.conn.recv(1024).decode()
        if query_id == self.user_id:
            self.conn.sendall("Cannot use your own ID.".encode())
            logging.warning(f"User {self.user_id} attempted to use their own ID. Command failed.")
            
            return

        if not self.user_id_manager.id_exists(query_id):
            self.conn.sendall("ID not found.".encode())
            logging.warning(f"ID {query_id} not found.")
            
            return
        
        target_addr = self.user_id_manager.get_addr(query_id)
        if target_addr is None:
            logging.error(f"Failed to get address for ID {query_id}")
            self.conn.sendall("Failed to get address.".encode())
        else:
            self.conn.sendall('Address located'.encode())
            response = f"{target_addr[0]}:{target_addr[1]}"
            self.conn.sendall(response.encode())
            logging.info(f"Sent address {response} to client {self.addr}")

    def check_id_existence(self):
        query_id = self.conn.recv(1024).decode()
        logging.info(f"Received ID check request from IP: {self.addr[0]}, Port: {self.addr[1]}")
        response = "ID does not exist." if not self.user_id_manager.id_exists(query_id) else f"ID {query_id} exists with address {self.user_id_manager.client_ids[query_id]}"
        self.conn.sendall(response.encode())

    def ping(self):
        logging.info(f"Ping received from client {self.addr}")
        self.conn.sendall(b"Pong")

    def __del__(self):
        print('ClientHandler deleted')


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    HOST = '127.0.0.1'
    PORT = 65431

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        logging.info(f"Server listening on {HOST}:{PORT}")
        user_id_manager = UserIDManager()
        while True:
            conn, addr = server_socket.accept()
            # How do we make 
            client_handler = ClientHandler(conn, addr, user_id_manager)
            client_handler.start()

