import socketio
import asyncio
import pyaudio
import ffmpeg
import cv2

from flask_socketio import send
from flask_socketio.namespace import Namespace as FlaskNamespace
from socketio import ClientNamespace
from threading import Thread

from client.encryption import KeyGenerators, KeyGenFactory, EncryptSchemes, EncryptFactory
from client.util import ClientState, display_message

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
        if self.cls.client.state == ClientState.CONNECTED:
            self.cls.client.state = ClientState.LIVE


class TestClientNamespace(ClientNamespace):

    def __init__(self, namespace, cls, *kwargs):
        super().__init__(namespace)
        self.cls = cls

    def on_connect(self):
        display_message(self.cls.user_id, "Connected to /test")

    def on_message(self, user_id, msg):
        msg = '/test: ' + msg

        async def disp():
            display_message(user_id, msg)
        asyncio.run(disp())

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
        if self.cls.client.state == ClientState.CONNECTED:
            self.cls.client.state = ClientState.LIVE


class AVClientNamespace(ClientNamespace):

    def __init__(self, namespace, cls: type, av,
                 frontend_socket: socketio.Client):
        super().__init__(namespace)
        self.cls: type = cls
        self.av: AV = av
        self.frontend_socket: socketio.Client = frontend_socket
        print("created AVClientNamespace", self.cls, self.av)

    def on_connect(self):
        pass

    def on_message(self, user_id, msg):
        pass

    def send(self, msg):
        self.cls.send_message(msg, namespace=self.namespace)

# endregion


# region --- Key Distributions ---

class KeyClientNamespace(AVClientNamespace):

    def on_connect(self):
        super().on_connect()
        self.key_idx = 0

        async def gen_keys():
            await asyncio.sleep(2)
            while True:
                self.av.key_gen.generate_key(key_length=128)
                key = self.key_idx.to_bytes(
                    4, 'big') + self.av.key_gen.get_key().tobytes()
                self.key_idx += 1

                await self.av.key_queue[self.cls.user_id]
                [self.namespace].put(key)

                await asyncio.sleep(1)

        Thread(target=asyncio.run, args=(gen_keys(),)).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)

# endregion


# region --- Audio ---

class AudioClientNamespace(AVClientNamespace):

    def on_connect(self):
        super().on_connect()
        audio = pyaudio.PyAudio()
        self.stream = audio.open(format=pyaudio.paInt16, channels=1,
                                 rate=self.av.sample_rate, output=True,
                                 frames_per_buffer=self.av.frames_per_buffer)
        self.stream.start_stream()

        async def send_audio():
            await asyncio.sleep(2)
            audio = pyaudio.PyAudio()
            stream = audio.open(format=pyaudio.paInt16, channels=1,
                                rate=self.av.sample_rate, input=True,
                                frames_per_buffer=self.av.frames_per_buffer)

            while True:
                cur_key_idx, key = self.av.key

                data = stream.read(self.av.frames_per_buffer,
                                   exception_on_overflow=False)

                if self.av.encryption is not None:
                    data = self.av.encryption.encrypt(data, key)
                self.send(cur_key_idx.to_bytes(4, 'big') + data)
                await asyncio.sleep(self.av.audio_wait)

        Thread(target=asyncio.run, args=(send_audio(),)).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)

        async def handle_message():
            if user_id == self.cls.user_id:
                return

            cur_key_idx, key = self.av.key

            if (int.from_bytes(msg[:4], 'big') != cur_key_idx):
                return
            data = msg[4:]

            data = self.av.encryption.decrypt(data, key)

            self.stream.write(
                data, num_frames=self.av.frames_per_buffer,
                exception_on_underflow=False)

        asyncio.run(handle_message())

# endregion


# region --- Video ---

class VideoClientNamespace(AVClientNamespace):

    def on_connect(self):
        super().on_connect()
        inpipe = ffmpeg.input('pipe:')
        self.output = ffmpeg.output(
            inpipe, 'pipe:', format='rawvideo', pix_fmt='rgbx')

        async def send_video():
            await asyncio.sleep(2)
            cap = cv2.VideoCapture(0)

            inpipe = ffmpeg.input(
                'pipe:',
                format='rawvideo',
                pix_fmt='rgbx',
                s='{}x{}'.format(
                    self.av.video_shape[1], self.av.video_shape[0]),
                r=self.av.frame_rate,
            )

            output = ffmpeg.output(
                inpipe, 'pipe:', vcodec='libx264', f='ismv',
                preset='ultrafast', tune='zerolatency')

            while True:
                cur_key_idx, key = self.av.key

                _, image = cap.read()
                image = cv2.resize(
                    image, (self.av.video_shape[1], self.av.video_shape[0]))
                data = image.tobytes("hex", "rgb")

                data = output.run(
                    input=data, capture_stdout=True, quiet=True)[0]

                data = self.av.encryption.encrypt(data, key)
                self.send(cur_key_idx.to_bytes(4, 'big') + data)

                await asyncio.sleep(1 / self.av.frame_rate / 5)

        Thread(target=asyncio.run, args=(send_video(),)).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)

        async def handle_message():
            if user_id == self.cls.user_id:
                return
            cur_key_idx, key = self.av.key

            if (int.from_bytes(msg[:4], 'big') != cur_key_idx):
                return

            data = self.av.encryption.decrypt(msg[4:], key)

            # Data is now an ISMV format file in memory
            data = self.output.run(input=data, capture_stdout=True,
                                   quiet=True)[0]

            super().frontend_socket.emit(data, {'type': 'stream'})

        asyncio.run(handle_message())

# endregion


# region --- AV ---


class AV:
    namespaces = {
        # '/video_key'    : (BroadcastFlaskNamespace, KeyClientNamespace),
        # '/audio_key'    : (BroadcastFlaskNamespace, KeyClientNamespace),
        '/video': (BroadcastFlaskNamespace, VideoClientNamespace),
        '/audio': (BroadcastFlaskNamespace, AudioClientNamespace),
    }

    def __init__(self, cls, frontend_socket: socketio.Client,
                 encryption: EncryptSchemes.ABSTRACT = EncryptFactory().create_encrypt_scheme(EncryptSchemes.AES)):

        self.cls = cls

        self.key_gen = KeyGenFactory().create_key_generator(KeyGenerators.FILE)
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

        self.encryption: EncryptSchemes.ABSTRACT = encryption

        self.client_namespaces = generate_client_namespace(
            cls, self, frontend_socket)

        async def gen_keys():
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
    namespaces = test_namespaces if testing else AV.namespaces
    return {name: namespaces[name][0](name, cls) for name in namespaces}


def generate_client_namespace(cls, *args):
    namespaces = test_namespaces if testing else AV.namespaces
    return {name: namespaces[name][1](name, cls, *args) for name in namespaces}

# endregion
