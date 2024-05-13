import asyncio
import logging
from threading import Thread
from socketio import Client as SocketIOClient
from .base_namespaces import BroadcastFlaskNamespace
from .video_namespace import VideoClientNamespace
from .audio_namespace import AudioClientNamespace
from .test_namespaces import TestFlaskNamespace, TestClientNamespace
from client.encryption import EncryptSchemes, EncryptFactory, KeyGenerators, KeyGenFactory

logging.basicConfig(filename='./src/middleware/logs/client.log',
                    level=logging.INFO,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')


class AVController:
    namespaces = {
        # '/video_key'    : (BroadcastFlaskNamespace, KeyClientNamespace),
        # '/audio_key'    : (BroadcastFlaskNamespace, KeyClientNamespace),
        '/video': (BroadcastFlaskNamespace, VideoClientNamespace),
        '/audio': (BroadcastFlaskNamespace, AudioClientNamespace),
    }

    def __init__(self, client_socket, frontend_socket: SocketIOClient,
                 encryption_type: EncryptSchemes.ABSTRACT,
                 key_source: KeyGenerators.ABSTRACT):

        self.client_socket = client_socket
        self.client_namespaces = generate_client_namespace(client_socket=client_socket, av_controller=self, frontend_socket=frontend_socket)

        # Video
        display_shapes = [(720, 960, 3), (720, 1280, 3)]
        self.display_shape = display_shapes[0]
        video_shapes = [(120, 160, 3), (240, 320, 3),
                        (480, 640, 3), (720, 960, 3), (1080, 1920, 3)]
        self.video_shape = video_shapes[2]
        self.frame_rate = 15

        # Audio
        sample_rates = [8196, 44100]
        self.sample_rate = sample_rates[0]
        self.frames_per_buffer = self.sample_rate // 6
        self.audio_wait = 1 / 8

        # Encryption
        self.encryption: EncryptSchemes.ABSTRACT.value = EncryptFactory().create_encrypt_scheme(type=encryption_type)
        self.key_gen: KeyGenerators.ABSTRACT.value = KeyGenFactory().create_key_generator(type=key_source).set_key_length(length=128)
        self.key_buffer_size: int = 100
        self.keys: list[bytes] = []

        async def gen_keys():
            # TODO: these look the same, why do it like this?
            for i in range(self.key_buffer_size):
                self.key_gen.generate_key()
                self.keys.append((len(self.keys), self.key_gen.get_key()))

            while True:
                self.key_gen.generate_key()
                self.keys.append((len(self.keys), self.key_gen.get_key()))

                await asyncio.sleep(1)

        Thread(target=asyncio.run, args=(gen_keys(),)).start()


testing = False

test_namespaces = {
    '/test': (TestFlaskNamespace, TestClientNamespace),
}


def generate_flask_namespace(client_socket):
    namespaces = test_namespaces if testing else AVController.namespaces
    return {name: namespaces[name][0](namespace=name, client_socket=client_socket) for name in namespaces}


def generate_client_namespace(client_socket, av_controller, frontend_socket):
    namespaces = test_namespaces if testing else AVController.namespaces
    return {name: namespaces[name][1](namespace=name, client_socket=client_socket, av_controller=av_controller, frontend_socket=frontend_socket) for name in namespaces}
