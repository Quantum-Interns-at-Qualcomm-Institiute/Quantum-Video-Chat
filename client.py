import socket
import logging
import threading
import select
from PIL import Image, ImageFile
from io import BytesIO
from threading import Thread
import cv2
import time
import numpy as np
from encryption import EncryptionScheme, EncryptionFactory, KeyGeneratorFactory, KeyGenerator
import random
from bitarray import bitarray

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
            '5': (self.client.send_text, 'Send text'),
            '6': (self.client.send_image, 'Send image'),
            '7': (self.client.send_video, 'Send video')
        }
        self.use_peer = {
            '1': False,
            '2': False,
            '3': False,
            '4': False,
            '5': True,
            '6': True,
            '7': True
        }

    def handle_command(self, choice, client_socket):
        command = self.commands.get(choice, client_socket)
        if command:
            self.client.in_command = True
            command[0](client_socket)
            self.client.in_command = False
        else:
            print("Invalid command. Try again.")

    def process_command(self, command, client_socket):
        handlers = {
            '5': (self.client.receive_text, 'Receive text'),
            '6': (self.client.receive_image, 'Receive image'),
            '7': (self.client.receive_video, 'Receive video')
        }
        handler = handlers.get(command)
        if handler:
            self.client.in_command = True
            handler[0](client_socket)
            self.client.in_command = False
        else:
            if command == "Dummy message":
                client_socket.sendall(b"Dummy message")
            else:
                logging.warning(f"Unknown command {command} from client")

# --- Start API stuff ---
import requests
import logging

logging.basicConfig(filename='client.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
class ClientAPI:
    def __init__(self, api_base_url):
        self.api_base_url = api_base_url
        
    def post(self, endpoint, payload):
        try:
            response = requests.post(f"{self.api_base_url}{endpoint}", json=payload)
            if response.status_code == 501:
                logger.error("API not implemented yet.")
            return response.json()
        except Exception as e:
            logger.error(f"An error occurred while making a POST request: {e}")


class NewClient:
    def __init__(self, server_ip, server_port, api_base_url, encryption_scheme_type = 'DEBUG', key_generator_type = 'DEBUG'):
        logger.info(f"Initializing client with host: {server_ip}, port: {server_port}")
        self.host = server_ip
        self.port = server_port
        self.api = ClientAPI(api_base_url)
        
        with EncryptionFactory() as factory:
            self.encryption_scheme = factory.create_encryption_scheme(encryption_scheme_type)
            
        with KeyGeneratorFactory() as factory:
            self.key_generator = factory.create_key_generator(key_generator_type)

    
    def configure_security(self):
        self.api.post('/api/configure_security', {
            "encryption_scheme": self.encryption_scheme,
            # "key_generator": self.key_generator
        })

    def configure_security(self):
        logger.info("Configuring security settings.")
        try:
            response = self.api.post('/api/configure_security', {
                "encryption_scheme": self.encryption_scheme.get_name(),
                # Tempted to keep this out of the API, but if we're doing key pools they need to be on the same page
                # "key_generator": self.key_generator
            })
            if response.status_code == 501:
                logger.error("API component not implemented yet.")
            else:
                logger.info(f"Security configured with status code {response.status_code}")
        except Exception as e:
            logger.error(f"An error occurred while configuring security: {e}")
    
    def initiate_key_exchange(self):
        # Initiates the key exchange process by making an RPC call to the peer client
        pass
    
    def connect(self):
        logger.info("Attempting to connect.")
        self.configure_security()
        # Make this async/await so we can make sure key exchange goes through
        self.initiate_key_exchange()
# --- End API stuff ---
class OldClient:
    def __init__(self, host, port, encryption_scheme='XOR', key_generator = 'DEBUG'):
        self.host = host
        self.port = port
        self.user_id = None
        self.listening_socket = None
        self.peer_socket = None
        self.in_command = False
        self.frame = None
        self.peer_frame = None
        self.res = (160, 120)
        with EncryptionFactory() as factory:
            self.encryption_scheme = factory.create_encryption_scheme(encryption_scheme)
            
        with KeyGeneratorFactory() as factory:
            self.key_generator = factory.create_key_generator(key_generator)
        
        self.key: bitarray = None

    def start_listening(self):
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind((self.host, self.port+2))
        self.listening_socket.listen(1)
        logging.info(f"Listening on {self.host}:{self.port+2}")

    def listen_for_connections(self, _):
        self.start_listening()
        # while self.listening_socket:
        conn, addr = self.listening_socket.accept()
        self.peer_socket = conn
        self.handle_connection(conn)
        # self.peer_socket.close()
        
            # readable, _, _ = select.select([self.listening_socket], [], [], 0.1)
            # if readable:
            #     conn, addr = self.listening_socket.accept()
            #     self.handle_connection(conn)
            #     self.listening_socket.close()

    def handle_connection(self, conn):
        # with conn:
        logging.info(f"Connection established with {conn.getpeername()}")
        conn.sendall(b"Hello from client!")
        response = conn.recv(1024).decode()
        host, port = response.split(" ")[-1].split(":")
        # self.peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.peer_socket.connect((host, int(port)))
        self.peer_thread = Thread(target = self.handle_peer_commands, args = (conn,))
        self.peer_thread.start()
        # peer_thread.join()
            
    def handle_peer_commands(self, conn):
        while True:
            if self.in_command:
                continue
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
            # client_socket.listen(1)
            client_socket.sendall(f"Address: {self.host}:{self.port+2}".encode())
            response = client_socket.recv(1024).decode()
            logging.info(f"Handshake response: {response}")
            self.peer_socket = client_socket
            peer_thread = Thread(target = self.handle_peer_commands, args = (client_socket,))
            peer_thread.start()
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

    def generateKey(self, length):
        self.key_generator.generate_key(length=length)
        self.key = self.key_generator.get_key()

    def encrypt(self, text):
        return self.encryption_scheme.encrypt(text, self.key)
    
    def send_text(self, client_socket):
        plaintext = bitarray()
        text_input = input("Enter text: ").encode('utf-8')
        plaintext.frombytes(text_input)
        self.generateKey(len(plaintext))
        
        payload = (self.key + self.encrypt(plaintext)).to01()
        client_socket.sendall(payload.encode()) # Probably doesnt need the final encode here
    
    def receive_text(self, client_socket):
        data = client_socket.recv(1024).decode()
        decrypt_key = bitarray(data[:len(data)//2])
        encrypted_text = bitarray(data[len(data)//2:])
        
        decrypted = self.encryption_scheme.decrypt(encrypted_text, decrypt_key).to01()
        bytes_data = int(decrypted, 2).to_bytes((len(decrypted) + 7) // 8, byteorder='big')
        message = bytes_data.decode('utf-8')
        
        logging.info(f"Peer says: {message}")

    def send_image(self, client_socket):
        img_path = input("Enter image path: ")
        with Image.open(img_path) as image:
            width, height = image.size
            client_socket.sendall(f"{width} {height}".encode())
            client_socket.recv(1024)
            # client_socket.sendall(image.tobytes())
            with BytesIO() as output:
                image.save(output, format="JPEG")  # You can change the format if needed (e.g., PNG)
                image_bytes = output.getvalue()
                client_socket.sendall(image_bytes)
    
    def receive_image(self, client_socket):
        size = client_socket.recv(1024).decode().split(" ")
        size = (int(size[0]), int(size[1]))
        client_socket.sendall(b"Dummy message")
        client_socket.recv(1024)
        client_socket.sendall(b"Size received")
        image_bytes = client_socket.recv(40960000)
        print(len(image_bytes), size[0]*size[1])
        # image = Image.frombytes('RGB', size, message)
        with BytesIO(image_bytes) as input_buffer:
            image = Image.open(input_buffer)
            # image = Image.open(BytesIO(message))
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            image.show()
            logging.info(f"Peer sends: {image}")

    def send_video(self, client_socket):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.res[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.res[1])
        while True:
            ret, frame = cap.read()
            self.frame = frame
            if not ret:
                break
            message = cv2.imencode('.jpg', frame)[1].tostring()
            client_socket.sendall(message)
            # logging.info(f"Peer sends: {len(message)}")
            # time.sleep(0.1)
        cap.release()
        client_socket.sendall(b"End of video")

    def receive_video(self, client_socket):
        while True:
            message = b""
            while len(message) < self.res[0]*self.res[1]*3:
                message += client_socket.recv(4096000)
            if message == b"End of video":
                break
            # logging.info(f"Peer sends: {len(message)}")
            nparr = np.fromstring(message, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            self.peer_frame = frame

            # time.sleep(0.1)
        cv2.destroyAllWindows()




import random
# Main block
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    HOST = '127.0.0.1'
    # HOST = 'ENTER SERVER IP HERE'
    PORT = 65431
    # PORT = random.randint(60000, 70000)

    client = OldClient(HOST, PORT)
    # client.connect()
    client_thread = Thread(target = client.connect, args = ())
    client_thread.start()
    # cv2.resizeWindow("Peer", (client.res[0], client.res[1]))
    while True:
        # print(client.frame)
        if not client.frame is None and not client.peer_frame is None:
            # print(client.frame)
            cv2.imshow("Peer", client.peer_frame)
            cv2.imshow("Self", client.frame)
            cv2.waitKey(1)
        # time.sleep(0.1)
