import time
from abc import abstractmethod
from threading import Thread

import ffmpeg
import numpy as np
import pyaudio
from flask_socketio import send
from flask_socketio.namespace import Namespace as FlaskNamespace
from socketio import ClientNamespace

from shared.logging import get_logger

logger = get_logger(__name__)


def display_message(user_id, msg):
    logger.info("(%s): %s", user_id, msg)


# region --- Tests ---

class TestFlaskNamespace(FlaskNamespace):
    def __init__(self, namespace, cls):
        super().__init__(namespace)
        self.cls = cls
        self.namespace = namespace

    def on_connect(self):
        pass

    def on_message(self, user_id, msg):
        send((user_id, msg), broadcast=True)

    def on_disconnect(self):
        pass


class TestClientNamespace(ClientNamespace):
    def __init__(self, namespace, cls, *kwargs):
        super().__init__(namespace)
        self.cls = cls

    def on_connect(self):
        display_message(self.cls.user_id, "Connected to /test")

    def on_message(self, user_id, msg):
        msg = '/test: ' + msg
        display_message(user_id, msg)

# endregion


# region --- General ---

class BroadcastFlaskNamespace(FlaskNamespace):
    def __init__(self, namespace, cls):
        super().__init__(namespace)
        self.cls = cls
        self.namespace = namespace

    def on_connect(self):
        pass

    def on_message(self, user_id, msg):
        send((user_id, msg), broadcast=True, include_self=False)

    def on_disconnect(self):
        pass


class AVClientNamespace(ClientNamespace):
    def __init__(self, namespace, cls, av):
        super().__init__(namespace)
        self.cls = cls
        self.av = av

    def on_connect(self):
        pass

    def on_message(self, user_id, msg):
        pass

    def send(self, msg):
        self.cls.send_message(msg, namespace=self.namespace)

# endregion


# region --- Key Distribution ---

class KeyClientNamespace(AVClientNamespace):
    def on_connect(self):
        super().on_connect()
        self.key_idx = 0

        def gen_keys():
            time.sleep(2)
            while True:
                self.av.key_gen.generate_key(key_length=128)
                key = self.key_idx.to_bytes(4, 'big') + self.av.key_gen.get_key().tobytes()
                self.key_idx += 1
                self.av.key_queue[self.cls.user_id][self.namespace].put(key)
                time.sleep(1)

        Thread(target=gen_keys, daemon=True).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)

# endregion


# region --- Audio ---

class AudioClientNamespace(AVClientNamespace):
    def on_connect(self):
        super().on_connect()
        audio = pyaudio.PyAudio()
        self.stream = audio.open(
            format=pyaudio.paInt16, channels=1,
            rate=self.av.sample_rate, output=True,
            frames_per_buffer=self.av.frames_per_buffer)
        self.stream.start_stream()

        def send_audio():
            time.sleep(2)
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16, channels=1,
                rate=self.av.sample_rate, input=True,
                frames_per_buffer=self.av.frames_per_buffer)

            while True:
                with self.av._key_lock:
                    cur_key_idx, key = self.av.key
                # Always read from mic to drain the buffer even when muted.
                data = stream.read(self.av.frames_per_buffer, exception_on_overflow=False)
                if not self.av.mute_audio:
                    if self.av.encryption is not None:
                        data = self.av.encryption.encrypt(data, key)
                    self.send(cur_key_idx.to_bytes(4, 'big') + data)
                time.sleep(self.av.audio_wait)

        Thread(target=send_audio, daemon=True).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)

        if user_id == self.cls.user_id:
            return
        with self.av._key_lock:
            cur_key_idx, key = self.av.key
        if int.from_bytes(msg[:4], 'big') != cur_key_idx:
            return
        data = self.av.encryption.decrypt(msg[4:], key)
        self.stream.write(data, num_frames=self.av.frames_per_buffer,
                          exception_on_underflow=False)

# endregion


# region --- Video ---

class VideoClientNamespace(AVClientNamespace):
    """
    Base video namespace. Subclasses must set `pix_fmt` and implement
    `_tobytes(image)` and `_handle_received_frame(user_id, raw_data)`.
    """
    pix_fmt = 'rgb24'

    def _tobytes(self, image):
        return image.tobytes()

    @abstractmethod
    def _handle_received_frame(self, user_id, raw_data: bytes):
        """Called with the decoded (pre-decryption pipeline) video bytes."""
        pass

    def _handle_self_frame(self, image) -> None:
        """Called with the raw numpy image after capture/generation, before encryption.
        Override in subclasses to preview the outgoing feed locally."""
        pass

    def on_connect(self):
        import cv2
        super().on_connect()
        inpipe = ffmpeg.input('pipe:')
        self.output = ffmpeg.output(
            inpipe, 'pipe:', format='rawvideo', pix_fmt=self.pix_fmt)

        def send_video():
            time.sleep(2)
            h, w = self.av.video_shape[0], self.av.video_shape[1]

            # Only open the camera when debug video mode is off
            cap = None if self.av.debug_video else cv2.VideoCapture(0)

            inpipe = ffmpeg.input(
                'pipe:',
                format='rawvideo',
                pix_fmt=self.pix_fmt,
                s=f'{w}x{h}',
                r=self.av.frame_rate,
            )
            output = ffmpeg.output(
                inpipe, 'pipe:', vcodec='libx264', f='ismv',
                preset='ultrafast', tune='zerolatency')

            try:
                while True:
                    with self.av._key_lock:
                        cur_key_idx, key = self.av.key

                    if self.av.debug_video:
                        # Generate a loading-spinner frame instead of random noise.
                        # A rotating arc on a dark background — functionally identical
                        # to a camera frame on the wire, but visually a loading wheel.
                        image = np.zeros((h, w, 3), dtype=np.uint8)
                        image[:] = (30, 30, 30)  # dark gray background

                        cx, cy = w // 2, h // 2
                        radius = min(w, h) // 6
                        thickness = max(3, radius // 5)

                        # Subtle background ring (track)
                        cv2.ellipse(image, (cx, cy), (radius, radius),
                                    0, 0, 360, (60, 60, 60), thickness, cv2.LINE_AA)

                        # Rotating foreground arc — spins ~1 revolution per second
                        angle = (time.time() * 270) % 360
                        start = int(angle)
                        cv2.ellipse(image, (cx, cy), (radius, radius),
                                    0, start, start + 270,
                                    (220, 220, 220), thickness, cv2.LINE_AA)
                    else:
                        _, image = cap.read()
                        image = cv2.resize(image, (w, h))

                    # Let subclasses preview what we are about to send (e.g. show
                    # the debug frame or camera feed in the sender's own UI).
                    self._handle_self_frame(image)

                    data = self._tobytes(image)
                    data = output.run(input=data, capture_stdout=True, quiet=True)[0]
                    data = self.av.encryption.encrypt(data, key)
                    self.send(cur_key_idx.to_bytes(4, 'big') + data)
                    time.sleep(1 / self.av.frame_rate / 5)
            finally:
                if cap is not None:
                    cap.release()

        Thread(target=send_video, daemon=True).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)

        if user_id == self.cls.user_id:
            return
        with self.av._key_lock:
            cur_key_idx, key = self.av.key
        if int.from_bytes(msg[:4], 'big') != cur_key_idx:
            return
        data = self.av.encryption.decrypt(msg[4:], key)
        data = self.output.run(input=data, capture_stdout=True, quiet=True)[0]
        self._handle_received_frame(user_id, data)

# endregion
