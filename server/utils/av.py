import numpy as np
from threading import Thread, Lock, Event

from shared.av.namespaces import (
    TestFlaskNamespace, TestClientNamespace,
    BroadcastFlaskNamespace, AVClientNamespace,
    KeyClientNamespace, AudioClientNamespace,
    VideoClientNamespace,
    display_message,
)
from shared.encryption import create_encrypt_scheme, create_key_generator
from shared.config import (
    VIDEO_SHAPE, DISPLAY_SHAPE, FRAME_RATE,
    SAMPLE_RATE, FRAMES_PER_BUFFER, AUDIO_WAIT,
    KEY_LENGTH, _scheme_name, _keygen_name,
)


# region --- Server-specific Video Namespace ---

class ServerVideoClientNamespace(VideoClientNamespace):
    """Stores decoded video frames in cls.video for display in the main thread."""
    pix_fmt = 'rgb24'

    def _tobytes(self, image):
        return image.tobytes()

    def _handle_received_frame(self, user_id, raw_data: bytes):
        data = np.frombuffer(raw_data, dtype=np.uint8).reshape(self.av.video_shape)
        self.cls.video[user_id] = data

# endregion


# region --- AV ---

class AV:
    namespaces = {
        '/video': (BroadcastFlaskNamespace, ServerVideoClientNamespace),
        '/audio': (BroadcastFlaskNamespace, AudioClientNamespace),
    }

    def __init__(self, cls, encryption=None):
        if encryption is None:
            encryption = create_encrypt_scheme(_scheme_name)
        self.cls = cls

        self.key_gen = create_key_generator(_keygen_name)
        self.key_gen.generate_key(key_length=KEY_LENGTH)

        self.display_shape = DISPLAY_SHAPE
        self.video_shape = VIDEO_SHAPE
        self.frame_rate = FRAME_RATE

        self.sample_rate = SAMPLE_RATE
        self.frames_per_buffer = FRAMES_PER_BUFFER
        self.audio_wait = AUDIO_WAIT

        self.key = 0, self.key_gen.get_key()
        self.encryption = encryption
        self._key_lock = Lock()
        self._key_stop = Event()

        self.client_namespaces = generate_client_namespace(cls, self)

        def _rotate_keys():
            key_idx = 0
            while not self._key_stop.is_set():
                self.key_gen.generate_key(key_length=KEY_LENGTH)
                with self._key_lock:
                    self.key = key_idx, self.key_gen.get_key()
                key_idx += 1
                self._key_stop.wait(timeout=1)

        Thread(target=_rotate_keys, daemon=True).start()

# endregion


# region --- Generators ---

testing = False

test_namespaces = {
    '/test': (TestFlaskNamespace, TestClientNamespace),
}


def generate_flask_namespace(cls):
    namespaces = test_namespaces if testing else AV.namespaces
    return {name: namespaces[name][0](name, cls) for name in namespaces}


def generate_client_namespace(cls, *args):
    namespaces = test_namespaces if testing else AV.namespaces
    return {name: namespaces[name][1](name, cls, *args) for name in namespaces}

# endregion
