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

    def handle_command(self, choice):
        if client.connected_to_peer and choice > 4:
            print("Invalid command. Try again.")
            return

        command = self.commands.get(choice)
        if command:
            command[0]()
        else:
            print("Invalid command. Try again.")

    # TODO: This is actually garbage. I'm instead going to make commands be a parameter in the constructor of the CommandHandler. Later when we have distinction between commands to the server and commands to the peer, we should just use two separate CommandHandlers initially created in main block
    def get_commands(self):
        if client.connected_to_peer:
            return self.commands
        return {i: self.commands[i] for i in ('1', '2', '3', '4')}



# TODO: Listening is a bit problematic. Ports for the clients seem to be (not exactly, but very close to) assigned in ascending order. In current implementation, peer_socket listen on whatever port server_socket is on, but just plus two. Ports can overlap if you're not careful.
# 
# We should instead somehow generate these numbers nicely and be able to communicate these to the server and forward to the peer, and then when the peer tries to connect to a client, the server gives them the correct listening port for the client.
#
# Right now, when the peer tries to connect with a client, the peer just gets the client's server_socket port, and then also manually adds two.
class Client:
    def __init__(self, host, port):
        self.server_host = host
        self.server_port = port
        self.user_id = None
        self.server_socket = None
        self.peer_socket = None
        self.connected_to_peer = False

    def start_listening(self):
        host, port = self.server_socket.getsockname()
        self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logging.info(f"Peer socket created on {host}:{port+2}")
        self.peer_socket.bind((host, port+2))
        self.peer_socket.listen(1)
        logging.info(f"Listening on {host}:{port+2}")

    def listen_for_connections(self):
        self.start_listening()
        while self.peer_socket:
            readable, _, _ = select.select([self.peer_socket], [], [], 0.1)
            if readable:
                conn, addr = self.peer_socket.accept()
                self.handle_connection(conn)
                
                # TEMP
                self.peer_socket.close()
                self.peer_socket = None
                return

    def handle_connection(self, conn):
        with conn:
            logging.info(f"Connection established with {conn.getpeername()}")
            conn.sendall(b"Hello from client!")
            response = conn.recv(1024).decode()
            logging.info(f"Received: {response}")

    def validate_id(self, id):
        self.server_socket.sendall(id.encode())
        response = self.server_socket.recv(1024).decode()
        if response == "ID not found.":
            logging.error("ID not found.")
            return False
        if response == 'Cannot use your own ID.':
            logging.error('Cannot use your own ID.')
            return False
        if response == 'Failed to get address.':
            logging.error('Failed to get address.')
            return False

        return True

    def connect(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            logging.info(f"Attempting connection to server {self.user_id}")
            self.server_socket.connect((self.server_host, self.server_port))
            self.user_id = self.server_socket.recv(1024).decode().split()[-1]
            logging.info(f"Connected from address {self.server_socket.getsockname()}.")
            logging.info(f"Received user ID {self.user_id} from server")
            command_handler = CommandHandler(self)
            while True:
                print()
                for key, value in command_handler.get_commands().items():
                    print(f"{key}) {value[1]}")

                choice = input("Select a command: ")
                self.server_socket.sendall(choice.encode())
                command_handler.handle_command(choice)
        except Exception as e:
            logging.error(f"Exception while communicating with server: {str(e)}", exc_info=True)
        finally:
            self.server_socket.close()
            if self.peer_socket:
                self.peer_socket.close()
            logging.info("Connection closed")

    def connect_to_client_by_id(self):
        id = input("Enter the ID of the client to connect to: ")
        if not self.validate_id(id):
            return
        response = self.server_socket.recv(1024).decode()
        target_host, target_port = response.split(":")
        self.handshake_with_client(target_host, int(target_port) + 2)

        # TEMP
        self.peer_socket.close()
        self.peer_socket = None

    def handshake_with_client(self, host, port):
        self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            logging.info(f"Attempting connection to {(host,port)}")
            self.peer_socket.connect((host, port))
            self.peer_socket.sendall(b"Hello!")
            response = self.peer_socket.recv(1024).decode()
            logging.info(f"Handshake response: {response}")
        except Exception as e:
            logging.error(f"Exception while handshaking with client: {str(e)}", exc_info=True)

    def query_id(self):
        id = input("Enter a user ID to query: ")
        self.server_socket.sendall(id.encode())
        response = self.server_socket.recv(1024).decode()
        logging.info(f"Server response: {response}")

    def ping_server(self):
        response = self.server_socket.recv(1024).decode()
        logging.info(f"Server response: {response}")

    # Close all connections
    def __del__(self):
        return


# Main block
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    HOST = '127.0.0.1'
    PORT = 65431

    client = Client(HOST, PORT)
    client.connect()
