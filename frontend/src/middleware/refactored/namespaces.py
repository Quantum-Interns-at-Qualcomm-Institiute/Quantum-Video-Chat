import asyncio
from threading import Thread
from time import time

from cv2 import VideoCapture, resize
from encryption import EncryptFactory, EncryptSchemes, KeyGenerators, KeyGenFactory
from eventlet import sleep
from ffmpeg import input as ffmpeg_input
from ffmpeg import output as ffmpeg_output
from flask_socketio import send
from flask_socketio.namespace import Namespace as FlaskNamespace
from pyaudio import PyAudio, paInt16
from socketio import Client as SocketIOClient
from socketio import ClientNamespace
from utils import ClientState, display_message


class AVClientNamespace(ClientNamespace):

    def __init__(self, namespace, client_socket, av_controller,
                 frontend_socket: SocketIOClient):
        super().__init__(namespace=namespace)
        self.client_socket = client_socket
        self.av_controller = av_controller
        self.frontend_socket: SocketIOClient = frontend_socket
        print("created AVClientNamespace", self.client_socket, self.av_controller)

    def on_connect(self):
        pass

    def on_message(self, user_id, msg):
        pass

    def send(self, msg):
        self.client_socket.send_message(msg, namespace=self.namespace)


class VideoClientNamespace(AVClientNamespace):
    def on_connect(self):
        super().on_connect()
        inpipe1 = ffmpeg_input('pipe:')
        self.output = ffmpeg_output(inpipe1, 'pipe:', format='rawvideo', pix_fmt='rgba')

        class VideoThread(Thread):
            def __init__(self, namespace):
                super().__init__()
                self.namespace = namespace

                self.cap = VideoCapture(0)
                # width = 3 * self.av_controller.video_shape[1] // 2
                # height = 3 * self.av_controller.video_shape[0] // 2
                self.width = self.namespace.av_controller.video_shape[1]
                self.height = self.namespace.av_controller.video_shape[0]

                self.inpipe = ffmpeg_input(
                    'pipe:',
                    format='rawvideo',
                    pix_fmt='bgr24',
                    s=f'{self.width}x{self.height}',
                    r=self.namespace.av_controller.frame_rate,
                )

                self.output = ffmpeg_output(
                    self.inpipe, 'pipe:', vcodec='libx264', f='ismv',
                    preset='ultrafast', tune='zerolatency')

            def run(self):
                while True:
                    key_idx, key = self.namespace.av_controller.keys[-self.namespace.av_controller.key_buffer_size]

                    ret, image = self.cap.read()
                    if not ret:
                        continue
                    image = resize(image, (self.width, self.height))
                    data = image.tobytes()
                    print(f"Pre-sending video frame with key index {key_idx}")
                    start = time.time()

                    data = self.output.run(input=data, capture_stdout=True, quiet=True)[0]

                    end = time.time()
                    print(end - start)
                    print(f"Sending video frame with key index {key_idx}")
                    data = self.namespace.av_controller.encryption.encrypt(data, key)
                    msg = {'frame': key_idx.to_bytes(4, 'big') + data, 'width': self.width, 'height': self.height}
                    self.namespace.send(msg=msg)

                    sleep(1 / self.namespace.av_controller.frame_rate / 5)

        VideoThread(self).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)

        async def handle_message():
            if user_id == self.client_socket.user_id:
                return

            frame = msg['frame'][4:]
            height = msg['height']
            width = msg['width']

            key_idx = int.from_bytes(msg['frame'][:4], 'big')
            key = self.av_controller.keys[key_idx][1]

            data = self.av_controller.encryption.decrypt(frame, key)

            data = self.output.run(input=data, capture_stdout=True, quiet=True)[0]

            print(f"Sending frame of size {len(data)} to frontend")
            self.frontend_socket.emit('stream', {'frame': data, 'height': height, 'width': width})

        asyncio.run(handle_message())


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
        # TODO: use client.set_state()
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


class KeyClientNamespace(AVClientNamespace):

    def on_connect(self):
        super().on_connect()
        self.key_idx = 0

        async def gen_keys():
            await asyncio.sleep(2)
            while True:
                self.av_controller.key_gen.generate_key(key_length=128)
                key = self.key_idx.to_bytes(
                    4, 'big') + self.av_controller.key_gen.get_key().tobytes()
                self.key_idx += 1

                await self.av_controller.key_queue[self.client_socket.user_id]
                [self.namespace].put(key)

                await asyncio.sleep(1)

        Thread(target=asyncio.run, args=(gen_keys(),)).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)


class AudioClientNamespace(AVClientNamespace):

    def on_connect(self):
        super().on_connect()
        audio = PyAudio()
        self.stream = audio.open(format=paInt16, channels=1,
                                 rate=self.av_controller.sample_rate, output=True,
                                 frames_per_buffer=self.av_controller.frames_per_buffer)
        self.stream.start_stream()

        # class AudioThread(Thread):
        #     def __init__(self, namespace):
        #         super().__init__()
        #         self.namespace = namespace
        #         self.audio = PyAudio()
        #         self.stream = self.audio.open(format=paInt16, channels=1,
        #                                       rate=self.namespace.av_controller.sample_rate, input=True,
        #                                       frames_per_buffer=self.namespace.av_controller.frames_per_buffer)

        #     def run(self):
        #         while True:
        #             key_idx, key = self.namespace.av_controller.keys[-self.namespace.av_controller.key_buffer_size]

        #             data = self.stream.read(self.namespace.av_controller.frames_per_buffer,
        #                                     exception_on_overflow=False)

        #             if self.namespace.av_controller.encryption is not None:
        #                 data = self.namespace.av_controller.encryption.encrypt(data, key)
        #             self.namespace.send(key_idx.to_bytes(4, 'big') + data)
        #             sleep(self.namespace.av_controller.audio_wait)

        # AudioThread(self).start()

        async def send_audio():
            await asyncio.sleep(2)
            audio = PyAudio()
            stream = audio.open(format=paInt16, channels=1,
                                rate=self.av_controller.sample_rate, input=True,
                                frames_per_buffer=self.av_controller.frames_per_buffer)

            while True:
                key_idx, key = self.av_controller.keys[-self.av_controller.key_buffer_size]

                data = stream.read(self.av_controller.frames_per_buffer,
                                   exception_on_overflow=False)

                if self.av_controller.encryption is not None:
                    data = self.av_controller.encryption.encrypt(data, key)
                self.send(key_idx.to_bytes(4, 'big') + data)
                await asyncio.sleep(self.av_controller.audio_wait)

        Thread(target=asyncio.run, args=(send_audio(),)).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)

        async def handle_message():
            if user_id == self.client_socket.user_id:
                return

            key_idx = int.from_bytes(msg[:4], 'big')
            key = self.av_controller.keys[key_idx][1]
            data = msg[4:]

            data = self.av_controller.encryption.decrypt(data, key)
            self.stream.write(
                data, num_frames=self.av_controller.frames_per_buffer,
                exception_on_underflow=False)

        asyncio.run(handle_message())


class BroadcastFlaskNamespace(FlaskNamespace):
    def __init__(self, namespace, client_socket):
        super().__init__(namespace=namespace)
        self.client_socket = client_socket
        self.namespace = namespace

    def on_connect(self):
        pass

    def on_message(self, auth, msg):
        user_id, sess_token = auth
        user_id = user_id
        if not self.client_socket.verify_sess_token(*auth):
            return

        send((user_id, msg), broadcast=True, include_self=False)

    def on_disconnect(self):
        # TODO: use client.set_state
        if self.client_socket.client.state == ClientState.CONNECTED:
            self.client_socket.client.state = ClientState.LIVE


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


def generate_flask_namespace(client_socket, testing=False):
    namespaces = test_namespaces if testing else AVController.namespaces
    return {name: namespaces[name][0](namespace=name, client_socket=client_socket) for name in namespaces}


def generate_client_namespace(client_socket, av_controller, frontend_socket, testing=False):
    namespaces = test_namespaces if testing else AVController.namespaces
    return {name: namespaces[name][1](namespace=name, client_socket=client_socket, av_controller=av_controller, frontend_socket=frontend_socket) for name in namespaces}
