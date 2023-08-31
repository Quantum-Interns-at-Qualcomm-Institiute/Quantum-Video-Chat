import socket
import logging
import threading
import select
from threading import Thread

# Setup Logging
logging.basicConfig(level=logging.INFO)

class CommandHandler:
    def __init__(self, client):
        self.client = client
        self.commands = {
            '1': (self.client.query_id, 'Check if ID exists'),
            '2': (self.client.ping_server, 'Ping server'),
            '3': (self.client.connect_to_client_by_id, 'Connect to client'),
            '4': (self.client.listen_for_connections, 'Listen for connections'),
            '5': (self.client.send_text, 'Send text')
        }
        self.use_peer = {
            '1': False,
            '2': False,
            '3': False,
            '4': False,
            '5': True
        }

    def handle_command(self, choice, client_socket):
        command = self.commands.get(choice, client_socket)
        if command:
            command[0](client_socket)
        else:
            print("Invalid command. Try again.")

    def process_command(self, command, client_socket):
        handlers = {
            '5': (self.client.receive_text, 'Receive text')
        }
        handler = handlers.get(command)
        if handler:
            handler[0](client_socket)
        else:
            logging.warning(f"Unknown command {command} from client")


class Client:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.user_id = None
        self.listening_socket = None
        self.peer_socket = None

    def start_listening(self):
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind((self.host, self.port+2))
        self.listening_socket.listen(1)
        logging.info(f"Listening on {self.host}:{self.port+2}")

    def listen_for_connections(self, _):
        self.start_listening()
        # while self.listening_socket:
        conn, addr = self.listening_socket.accept()
        self.handle_connection(conn)
        self.listening_socket.close()
        
            # readable, _, _ = select.select([self.listening_socket], [], [], 0.1)
            # if readable:
            #     conn, addr = self.listening_socket.accept()
            #     self.handle_connection(conn)
            #     self.listening_socket.close()

    def handle_connection(self, conn):
        with conn:
            logging.info(f"Connection established with {conn.getpeername()}")
            conn.sendall(b"Hello from client!")
            response = conn.recv(1024).decode()
            logging.info(f"Received: {response}")
            peer_thread = Thread(target = self.handle_peer_commands, args = (conn,))
            peer_thread.start()
            peer_thread.join()
            
    def handle_peer_commands(self, conn):
        while True:
            command = conn.recv(1024).decode()
            if not command:
                if command != "":
                    logging.info(f"Bad command {command} from peer.")
            else:
                self.command_handler.process_command(command, conn)

    def validate_id(self, client_socket, id):
        # if id == self.user_id:
        #     logging.error("Cannot use your own ID.")
        #     return False

        client_socket.sendall(id.encode())
        response = client_socket.recv(1024).decode()
        if response == "ID not found.":
            logging.error("ID not found.")
            return None

        logging.info(f"ID {id} exists with address {response}")
        return response

    def connect(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            try:
                client_socket.connect((self.host, self.port))
                info = client_socket.recv(1024).decode().split()
                self.user_id, self.port = info[-2], int(info[-1])
                logging.info(f"Received user ID {self.user_id} and port number {self.port} from server")
                self.command_handler = CommandHandler(self)
                while True:
                    for key, value in self.command_handler.commands.items():
                        print(f"{key}) {value[1]}")

                    choice = input("Select a command: ")
                    to_socket = self.peer_socket if self.command_handler.use_peer[choice] else client_socket
                    to_socket.sendall(choice.encode())
                    self.command_handler.handle_command(choice, to_socket)
            except Exception as e:
                logging.error(f"Exception while communicating with server: {str(e)}", exc_info=True)
            finally:
                logging.info("Connection closed")

    def connect_to_client_by_id(self, client_socket):
        id = input("Enter the ID of the client to connect to: ")
        # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        response = self.validate_id(client_socket, id)
        if response == None:
            return

        target_host, target_port = response.split(":")
        logging.info(f"Connecting to {target_host}:{int(target_port)+2}...")
        self.handshake_with_client(target_host, int(target_port)+2)

    def handshake_with_client(self, host, port):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_socket.connect((host, port))
            client_socket.sendall(b"Hello!")
            response = client_socket.recv(1024).decode()
            logging.info(f"Handshake response: {response}")
            self.peer_socket = client_socket
        except Exception as e:
            logging.error(f"Exception while handshaking with client: {str(e)}", exc_info=True)

    def query_id(self, client_socket):
        id = input("Enter a user ID to query: ")
        # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.sendall(id.encode())
        response = client_socket.recv(1024).decode()
        logging.info(f"Server response: {response}")

    def ping_server(self, client_socket):
        # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        response = client_socket.recv(1024).decode()
        logging.info(f"Server response: {response}")

    def send_text(self, client_socket):
        text = input("Enter text: ")
        client_socket.sendall(text.encode())
    
    def receive_text(self, client_socket):
        message = client_socket.recv(1024).decode()
        logging.info(f"Peer says: {message}")




import random
# Main block
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    HOST = '127.0.0.1'
    PORT = 65431
    # PORT = random.randint(60000, 70000)

    client = Client(HOST, PORT)
    client.connect()
