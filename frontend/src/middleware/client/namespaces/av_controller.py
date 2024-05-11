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

    def __init__(self, cls, frontend_socket: SocketIOClient,
                 encryption: EncryptSchemes.ABSTRACT = EncryptFactory().create_encrypt_scheme(EncryptSchemes.AES)):

        self.cls = cls

        self.key_gen = KeyGenFactory().create_key_generator(KeyGenerators.DEBUG)
        self.key_gen.generate_key(key_length=128)

        display_shapes = [(720, 960, 3), (720, 1280, 3)]
        self.display_shape = display_shapes[0]
        video_shapes = [(120, 160, 3), (240, 320, 3),
                        (480, 640, 3), (720, 960, 3), (1080, 1920, 3)]
        self.video_shape = video_shapes[2]
        self.frame_rate = 15

        sample_rates = [8196, 44100]
        self.sample_rate = sample_rates[0]
        self.frames_per_buffer = self.sample_rate // 6
        self.audio_wait = 1 / 8

        # self.key = self.key_gen.get_key().tobytes()

        self.encryption: EncryptSchemes.ABSTRACT = encryption

        self.client_namespaces = generate_client_namespace(
            cls, self, frontend_socket)

        self.key_buffer_size = 100
        self.keys = []
        async def gen_keys():
            for i in range(self.key_buffer_size):
                self.key_gen.generate_key(key_length=128)
                self.keys.append((len(self.keys), self.key_gen.get_key().tobytes()))
                
            while True:
                self.key_gen.generate_key(key_length=128)
                self.keys.append((len(self.keys), self.key_gen.get_key().tobytes()))

                await asyncio.sleep(1)

        Thread(target=asyncio.run, args=(gen_keys(),)).start()


testing = False

test_namespaces = {
    '/test': (TestFlaskNamespace, TestClientNamespace),
}


def generate_flask_namespace(cls):
    namespaces = test_namespaces if testing else AVController.namespaces
    return {name: namespaces[name][0](name, cls) for name in namespaces}


def generate_client_namespace(cls, *args):
    namespaces = test_namespaces if testing else AVController.namespaces
    return {name: namespaces[name][1](name, cls, *args) for name in namespaces}
