import asyncio
from threading import Thread

import cv2
import ffmpeg
import numpy as np
import pyaudio
from encryption import EncryptionFactory, EncryptionScheme, KeyGeneratorFactory
from flask_socketio import send
from flask_socketio.namespace import Namespace as FlaskNamespace
from socketio import ClientNamespace
from states import ClientState
from utils import display_message


class TestFlaskNamespace(FlaskNamespace):
    def __init__(self, namespace, cls):
        super().__init__(namespace)
        self.cls = cls
        self.namespace = namespace

    def on_connect(self):
        pass

    def on_message(self, auth, msg):
        user_id, sess_token = auth
        user_id = user_id
        if not self.cls.verify_sess_token(*auth):
            return

        send((user_id, msg), broadcast=True)

    def on_disconnect(self):
        # self.cls.logger.info(f"Client disconnected from namespace {self.namespace}.")
        # TODO: use client.set_state()
        if self.cls.client.state == ClientState.CONNECTED:
            self.cls.client.state = ClientState.LIVE


class TestClientNamespace(ClientNamespace):

    def __init__(self, namespace, cls, *kwargs):
        super().__init__(namespace)
        self.cls = cls

    def on_connect(self):
        # self.cls.logger.info(f"Socket connection established to endpoint {self.cls.endpoint} on namespace /test")
        display_message(self.cls.user_id, "Connected to /test")

    def on_message(self, user_id, msg):
        msg = '/test: ' + msg
        # self.cls.logger.info(f"Received /test message from user {user_id}: {msg}")

        async def disp():
            display_message(user_id, msg)
        asyncio.run(disp())


class AVClientNamespace(ClientNamespace):

    def __init__(self, namespace, cls, av):
        super().__init__(namespace)
        self.cls = cls
        self.av = av  # No type safety since that creates circular dependency
        print("created AVClientNamespace", self.cls, self.av)

    def on_connect(self):
        print("on_connect")

    def on_message(self, user_id, msg):
        pass

    def send(self, msg):
        self.cls.send_message(msg, namespace=self.namespace)


class KeyClientNamespace(AVClientNamespace):

    def on_connect(self):
        super().on_connect()
        self.key_idx = 0

        async def gen_keys():
            await asyncio.sleep(2)
            print('send_keys')
            while True:
                self.av.key_gen.generate_key(key_length=128)
                key = self.key_idx.to_bytes(
                    4, 'big') + self.av.key_gen.get_key().tobytes()
                self.key_idx += 1

                await self.av.key_queue[self.cls.user_id][self.namespace].put(key)
                await asyncio.sleep(1)

        Thread(target=asyncio.run, args=(gen_keys(),)).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)
        # asyncio.run(self.av.key_queue[user_id][self.namespace].put(msg))


class AudioClientNamespace(AVClientNamespace):

    def on_connect(self):
        super().on_connect()
        audio = pyaudio.PyAudio()
        self.stream = audio.open(format=pyaudio.paInt16, channels=1, rate=self.av.sample_rate,
                                 output=True, frames_per_buffer=self.av.frames_per_buffer)
        self.stream.start_stream()

        async def send_audio():
            await asyncio.sleep(2)
            audio = pyaudio.PyAudio()
            stream = audio.open(format=pyaudio.paInt16, channels=1, rate=self.av.sample_rate,
                                input=True, frames_per_buffer=self.av.frames_per_buffer)

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

            key_idx = int.from_bytes(msg[:4], 'big')
            if (key_idx != cur_key_idx):
                return
            data = msg[4:]

            data = self.av.encryption.decrypt(data, key)

            self.stream.write(
                data, num_frames=self.av.frames_per_buffer, exception_on_underflow=False)

        asyncio.run(handle_message())


class VideoClientNamespace(AVClientNamespace):

    def on_connect(self):
        super().on_connect()
        inpipe = ffmpeg.input('pipe:')
        self.output = ffmpeg.output(
            inpipe, 'pipe:', format='rawvideo', pix_fmt='rgb24')

        async def send_video():
            await asyncio.sleep(2)
            cap = cv2.VideoCapture(0)

            # doesn't work
            # cam.set(cv2.CAP_PROP_FRAME_WIDTH, video_shape[1])
            # cam.set(cv2.CAP_PROP_FRAME_HEIGHT, video_shape[0])

            inpipe = ffmpeg.input(
                'pipe:',
                format='rawvideo',
                pix_fmt='rgb24',
                s='{}x{}'.format(
                    self.av.video_shape[1], self.av.video_shape[0]),
                r=self.av.frame_rate,
            )

            output = ffmpeg.output(
                inpipe, 'pipe:', vcodec='libx264', f='ismv', preset='ultrafast', tune='zerolatency')

            while True:
                cur_key_idx, key = self.av.key

                result, image = cap.read()
                image = cv2.resize(
                    image, (self.av.video_shape[1], self.av.video_shape[0]))
                data = image.tobytes()

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

            key_idx = int.from_bytes(msg[:4], 'big')
            if (key_idx != cur_key_idx):
                return
            data = msg[4:]

            data = self.av.encryption.decrypt(data, key)

            data = self.output.run(
                input=data, capture_stdout=True, quiet=True)[0]

            data = np.frombuffer(data, dtype=np.uint8).reshape(
                self.av.video_shape)

            self.cls.video[user_id] = data

        asyncio.run(handle_message())


class BroadcastFlaskNamespace(FlaskNamespace):
    def __init__(self, namespace, cls):
        super().__init__(namespace)
        self.cls = cls
        self.namespace = namespace

    def on_connect(self):
        pass

    def on_message(self, auth, msg):
        user_id, sess_token = auth
        user_id = user_id
        if not self.cls.verify_sess_token(*auth):
            return

        # Change include_self to True if you want your own video to be displayed
        send((user_id, msg), broadcast=True, include_self=False)

    def on_disconnect(self):
        # TODO: these lines were erroring, this fix isn't optimal
        for client in self.cls.users:
            if client.state == ClientState.CONNECTED.value:
                client.state = ClientState.LIVE.value


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


test_namespaces = {
    '/test': (TestFlaskNamespace, TestClientNamespace),
}


def generate_flask_namespace(cls, testing=False):
    namespaces = test_namespaces if testing else AVController.namespaces
    return {name: namespaces[name][0](name, cls) for name in namespaces}


def generate_client_namespace(cls, testing=False, *args):
    namespaces = test_namespaces if testing else AVController.namespaces
    return {name: namespaces[name][1](name, cls, *args) for name in namespaces}
