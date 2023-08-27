import socket
import logging
import threading
import select

# Setup Logging
logging.basicConfig(level=logging.INFO)

class CommandHandler:
    def __init__(self, client):
        self.client = client
        self.commands = {
            '1': (self.client.query_id, 'Check if ID exists'),
            '2': (self.client.ping_server, 'Ping server'),
            '3': (self.client.connect_to_client_by_id, 'Connect to client'),
            '4': (self.client.listen_for_connections, 'Listen for connections')
        }

    def handle_command(self, choice, client_socket):
        command = self.commands.get(choice)
        if command:
            command[0](client_socket)
        else:
            print("Invalid command. Try again.")


class Client:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.user_id = None
        self.listening_socket = None

    def start_listening(self):
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind((self.host, self.port+2))
        self.listening_socket.listen(1)
        logging.info(f"Listening on {self.host}:{self.port}")

    def listen_for_connections(self, _):
        self.start_listening()
        while self.listening_socket:
            readable, _, _ = select.select([self.listening_socket], [], [], 0.1)
            if readable:
                conn, addr = self.listening_socket.accept()
                self.handle_connection(conn)

    def handle_connection(self, conn):
        with conn:
            logging.info(f"Connection established with {conn.getpeername()}")
            conn.sendall(b"Hello from client!")
            response = conn.recv(1024).decode()
            logging.info(f"Received: {response}")

    def validate_id(self, client_socket, id):
        # if id == self.user_id:
        #     logging.error("Cannot use your own ID.")
        #     return False

        client_socket.sendall(id.encode())
        response = client_socket.recv(1024).decode()
        if response == "ID not found.":
            logging.error("ID not found.")
            return False

        return True

    def connect(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            try:
                client_socket.connect((self.host, self.port))
                self.user_id = client_socket.recv(1024).decode().split()[-1]
                logging.info(f"Received user ID {self.user_id} from server")
                command_handler = CommandHandler(self)
                while True:
                    for key, value in command_handler.commands.items():
                        print(f"{key}) {value[1]}")

                    choice = input("Select a command: ")
                    client_socket.sendall(choice.encode())
                    command_handler.handle_command(choice, client_socket)
            except Exception as e:
                logging.error(f"Exception while communicating with server: {str(e)}", exc_info=True)
            finally:
                logging.info("Connection closed")

    def connect_to_client_by_id(self, client_socket):
        id = input("Enter the ID of the client to connect to: ")
        # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        if not self.validate_id(client_socket, id):
            return

        response = client_socket.recv(1024).decode()
        target_host, target_port = response.split(":")
        self.handshake_with_client(target_host, int(target_port))

    def handshake_with_client(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            try:
                client_socket.connect((host, port))
                client_socket.sendall(b"Hello!")
                response = client_socket.recv(1024).decode()
                logging.info(f"Handshake response: {response}")
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


# Main block
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    HOST = '127.0.0.1'
    PORT = 65431

    client = Client(HOST, PORT)
    client.connect()
