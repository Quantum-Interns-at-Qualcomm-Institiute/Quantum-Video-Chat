import time
from threading import Thread, Lock, Event

from shared.adapters import VideoSink
from shared.av.namespaces import (
    TestFlaskNamespace, TestClientNamespace,
    BroadcastFlaskNamespace, AVClientNamespace,
    KeyClientNamespace, AudioClientNamespace,
    VideoClientNamespace,
)
from shared.encryption import create_encrypt_scheme, create_key_generator
from shared.config import (
    VIDEO_SHAPE, DISPLAY_SHAPE, FRAME_RATE,
    SAMPLE_RATE, FRAMES_PER_BUFFER, AUDIO_WAIT,
    KEY_LENGTH, DEFAULT_ENCRYPT_SCHEME, DEFAULT_KEY_GENERATOR,
    DEBUG_VIDEO, MUTE_AUDIO,
    _VIDEO_WIDTH, _VIDEO_HEIGHT,
    _scheme_name, _keygen_name,
)


# region --- Client-specific Video Namespace ---

class ClientVideoClientNamespace(VideoClientNamespace):
    """Forwards decoded video frames to the Electron frontend via the adapter."""
    pix_fmt = 'rgb0'

    def _tobytes(self, image):
        import cv2
        import numpy as np
        # image is a numpy BGR array from OpenCV (or grayscale-equivalent for debug).
        # pix_fmt='rgb0' expects 4 bytes/pixel: R, G, B, 0x00 (zero-padded).
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        x = np.zeros((h, w, 1), dtype=np.uint8)
        return np.dstack([rgb, x]).tobytes()

    def _handle_received_frame(self, user_id, raw_data: bytes):
        self.av.adapter.send_frame(raw_data)

    def _handle_self_frame(self, image) -> None:
        """Convert the outgoing numpy image to RGBA and push it to the frontend
        so the local user sees exactly what is being sent (camera or debug frame)."""
        import cv2
        import numpy as np
        h, w = image.shape[:2]
        # Camera frames from OpenCV are BGR; debug frames are already RGB (gray).
        # Convert to RGB so colours display correctly in the browser canvas.
        if not self.av.debug_video:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # Add a fully-opaque alpha channel (required by ImageData in the frontend).
        alpha = np.full((h, w), 255, dtype=np.uint8)
        rgba = np.dstack([image, alpha])
        self.av.adapter.send_self_frame(rgba.tobytes(), w, h)

# endregion


# region --- AV ---

class AV:
    namespaces = {
        '/video': (BroadcastFlaskNamespace, ClientVideoClientNamespace),
        '/audio': (BroadcastFlaskNamespace, AudioClientNamespace),
    }

    def __init__(self, cls, adapter: VideoSink, encryption=None,
                 session_settings=None):
        """
        Parameters
        ----------
        session_settings : dict, optional
            When the local client is the *peer* (not the host), this dict
            carries the host's shared AV/encryption settings so both sides
            use matching configuration.  Keys:
                video_width, video_height, frame_rate,
                sample_rate, audio_wait,
                key_length, encrypt_scheme, key_generator
            ``debug_video`` is intentionally **never** included — it stays
            local to each client.
        """
        s = session_settings or {}

        # --- Shared settings (host dictates when session_settings provided) ---
        vw = s.get('video_width', _VIDEO_WIDTH)
        vh = s.get('video_height', _VIDEO_HEIGHT)
        scheme = s.get('encrypt_scheme', _scheme_name)
        keygen = s.get('key_generator', _keygen_name)
        key_length = s.get('key_length', KEY_LENGTH)

        if encryption is None:
            encryption = create_encrypt_scheme(scheme)

        self.cls = cls
        self.adapter = adapter

        self.key_gen = create_key_generator(keygen)
        self.key_gen.generate_key(key_length=key_length)

        self.video_shape = (vh, vw, 3)
        self.frame_rate = s.get('frame_rate', FRAME_RATE)

        self.sample_rate = s.get('sample_rate', SAMPLE_RATE)
        fpb = self.sample_rate // 6
        self.frames_per_buffer = fpb
        self.audio_wait = s.get('audio_wait', AUDIO_WAIT)

        # --- Local settings (never overridden by host) ---
        self.display_shape = DISPLAY_SHAPE
        self.debug_video = DEBUG_VIDEO
        self.mute_audio = MUTE_AUDIO

        self.key = 0, self.key_gen.get_key()
        self.encryption = encryption
        self._key_lock = Lock()
        self._key_stop = Event()
        self._key_length = key_length

        self.client_namespaces = generate_client_namespace(cls, self)

        def _rotate_keys():
            key_idx = 0
            while not self._key_stop.is_set():
                self.key_gen.generate_key(key_length=self._key_length)
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


def generate_client_namespace(cls, av):
    namespaces = test_namespaces if testing else AV.namespaces
    return {name: namespaces[name][1](name, cls, av) for name in namespaces}

# endregion
