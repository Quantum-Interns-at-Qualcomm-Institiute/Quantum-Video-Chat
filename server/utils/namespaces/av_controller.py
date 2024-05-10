import asyncio
import logging
from threading import Thread

from .base_namespaces import BroadcastFlaskNamespace
from .test_namespaces import TestClientNamespace, TestFlaskNamespace
from .audio_namespace import AudioClientNamespace
from .video_namespace import VideoClientNamespace
from utils.encryption import EncryptionFactory, EncryptionScheme, KeyGeneratorFactory

logging.basicConfig(filename='./logs/server.log', level=logging.DEBUG,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')


class AVController:
    namespaces = {
        # '/video_key'    : (BroadcastFlaskNamespace, KeyClientNamespace),
        # '/audio_key'    : (BroadcastFlaskNamespace, KeyClientNamespace),
        '/video': (BroadcastFlaskNamespace, VideoClientNamespace),
        '/audio': (BroadcastFlaskNamespace, AudioClientNamespace),
    }

    def __init__(self, cls, encryption: EncryptionScheme = EncryptionFactory().create_encryption_scheme("AES")):
        self.cls = cls

        self.key_gen = KeyGeneratorFactory().create_key_generator("FILE")
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

        self.key = self.key_gen.get_key().tobytes()

        self.encryption = encryption

        self.client_namespaces = generate_client_namespace(cls, self)

        async def gen_keys():
            print('send_keys')
            key_idx = 0
            while True:
                self.key_gen.generate_key(key_length=128)
                self.key = key_idx, self.key_gen.get_key().tobytes()
                key_idx += 1

                await asyncio.sleep(1)

        Thread(target=asyncio.run, args=(gen_keys(),)).start()

# endregion


# region --- Generators ---
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

# endregion
