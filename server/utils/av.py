"""Audio/video namespace management and encryption key rotation."""

import logging
from threading import Event, Lock, Thread

import numpy as np

from shared.av.namespaces import (
    AudioClientNamespace,
    BroadcastFlaskNamespace,
    TestClientNamespace,
    TestFlaskNamespace,
    VideoClientNamespace,
)
from shared.config import (
    AUDIO_WAIT,
    DISPLAY_SHAPE,
    FRAME_RATE,
    FRAMES_PER_BUFFER,
    KEY_LENGTH,
    SAMPLE_RATE,
    VIDEO_SHAPE,
    _keygen_name,
    _scheme_name,
)
from shared.encryption import (
    BB84KeyGenerator,
    create_encrypt_scheme,
    create_key_generator,
)

logger = logging.getLogger(__name__)


# region --- Server-specific Video Namespace ---

class ServerVideoClientNamespace(VideoClientNamespace):
    """Stores decoded video frames in cls.video for display in the main thread."""
    pix_fmt = "rgb24"

    def _tobytes(self, image):
        return image.tobytes()

    def _handle_received_frame(self, user_id, raw_data: bytes):
        data = np.frombuffer(raw_data, dtype=np.uint8).reshape(self.av.video_shape)
        self.cls.video[user_id] = data

# endregion


# region --- AV ---

class AV:
    """Manages AV namespaces and encryption key rotation."""

    namespaces = {  # noqa: RUF012
        "/video": (BroadcastFlaskNamespace, ServerVideoClientNamespace),
        "/audio": (BroadcastFlaskNamespace, AudioClientNamespace),
    }

    def __init__(self, cls, encryption=None):
        """Initialize AV with namespaces, encryption, and key rotation thread."""
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

        # BB84 QBER monitoring
        self.qber_monitor = None
        self._qber_event_callback = None
        self._is_bb84 = isinstance(self.key_gen, BB84KeyGenerator)

        if self._is_bb84:
            from shared.bb84.qber_monitor import QBERMonitor  # noqa: PLC0415
            self.qber_monitor = QBERMonitor()
            self.key_gen.set_metrics_callback(self.qber_monitor.record_round)

        self.client_namespaces = generate_client_namespace(cls, self)

        def _rotate_keys():
            key_idx = 0
            while not self._key_stop.is_set():
                self.key_gen.generate_key(key_length=KEY_LENGTH)

                # BB84: check if round was aborted (intrusion detected)
                if self._is_bb84 and hasattr(self.key_gen, "last_round_result"):
                    result = self.key_gen.last_round_result
                    if result and result.aborted:
                        logger.warning(
                            "BB84 key generation aborted: %s (QBER=%.4f)",
                            result.abort_reason, result.qber,
                        )
                        if self._qber_event_callback:
                            self._qber_event_callback("intrusion_detected", {
                                "qber": result.qber,
                                "reason": result.abort_reason,
                                "sifted_bits": result.sifted_bits,
                            })
                        # Retry faster — don't update key
                        self._key_stop.wait(timeout=0.5)
                        continue

                with self._key_lock:
                    self.key = key_idx, self.key_gen.get_key()
                key_idx += 1

                if self._is_bb84 and self._qber_event_callback:
                    result = self.key_gen.last_round_result
                    if result:
                        self._qber_event_callback("key_redistributed", {
                            "qber": result.qber,
                            "sifted_bits": result.sifted_bits,
                            "final_key_bits": result.final_key_bits,
                            "duration": result.duration_seconds,
                        })

                rotation_interval = 3.0 if self._is_bb84 else 1.0
                self._key_stop.wait(timeout=rotation_interval)

        Thread(target=_rotate_keys, daemon=True).start()

    def set_qber_event_callback(self, callback):
        """Register callback(event_type, data) for QBER events."""
        self._qber_event_callback = callback

# endregion


# region --- Generators ---

testing = False

test_namespaces = {
    "/test": (TestFlaskNamespace, TestClientNamespace),
}


def generate_flask_namespace(cls):
    """Create Flask-side AV namespaces for the given server class."""
    namespaces = test_namespaces if testing else AV.namespaces
    return {name: namespaces[name][0](name, cls) for name in namespaces}


def generate_client_namespace(cls, *args):
    """Create client-side AV namespaces for the given server class."""
    namespaces = test_namespaces if testing else AV.namespaces
    return {name: namespaces[name][1](name, cls, *args) for name in namespaces}

# endregion
