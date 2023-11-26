# import argparse
# import asyncio
# import logging
# from threading import Thread
# import math
# import pyaudio
# import platform
# import time
# from bitarray import bitarray
# import io

# import sounddevice as sd

# import cv2
# import av
# import ffmpeg

# import numpy as np
# from aiortc import (
#     RTCIceCandidate,
#     RTCPeerConnection,
#     RTCSessionDescription,
#     RTCDataChannel,
# )

# from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling

# import sys
# import pathlib

# sys.path.insert(0, pathlib.Path(__file__).parent.parent.resolve().as_posix())
# from utils.encryption import AESEncryption, RandomKeyGenerator, KeyGeneratorFactory, EncryptionFactory, EncryptionScheme

# async def run(pc: RTCPeerConnection, signaling, role, encryption: EncryptionScheme=None):
#     key_gen = KeyGeneratorFactory().create_key_generator("RANDOM")
#     key_gen.generate_key(key_length=128)

#     display_shapes = [(720, 960, 3), (720, 1280, 3)]
#     display_shape = display_shapes[0]
#     video_shapes = [(120, 160, 3), (240, 320, 3), (480, 640, 3), (720, 960, 3), (1080, 1920, 3)]
#     video_shape = video_shapes[2]
#     frame_rate = 15

#     sample_rates = [8196, 44100]
#     sample_rate = sample_rates[0]
#     frames_per_buffer = sample_rate//6
#     audio_wait = 1/8

#     key_queue = {"video": asyncio.Queue(), "audio": asyncio.Queue()}
#     key = {"video": key_gen.get_key().tobytes(), "audio": key_gen.get_key().tobytes()}
#     async def send_keys(key_channel, key_queue):
#         print('send_keys')
#         while True:
#             key_gen.generate_key(128)
#             key = key_gen.get_key().tobytes()
#             key_channel.send(key)
#             await key_queue.put(key)
#             print(key, key_queue.qsize())
#             await asyncio.sleep(1)

#     async def send_video(video_channel):
#         cap = cv2.VideoCapture(1)
        
#         # doesn't work
#         # cam.set(cv2.CAP_PROP_FRAME_WIDTH, video_shape[1])
#         # cam.set(cv2.CAP_PROP_FRAME_HEIGHT, video_shape[0])

#         inpipe = ffmpeg.input(
#             'pipe:', 
#             format='rawvideo', 
#             pix_fmt='rgb24', 
#             s='{}x{}'.format(video_shape[1], video_shape[0]), 
#             r=frame_rate,
#         )

#         output = ffmpeg.output(inpipe, 'pipe:', vcodec='libx264', f='ismv', preset='ultrafast', tune='zerolatency')

#         while True:
#             start = time.time()

#             if not key_queue["video"].empty():
#                 key["video"] = await key_queue["video"].get()

#             result, image = cap.read()
#             image = cv2.resize(image, (video_shape[1], video_shape[0]))
#             data = image.tobytes()

#             data = output.run(input=data, capture_stdout=True, quiet=True)[0]

#             if encryption is not None:
#                 data = encryption.encrypt(data, key["video"])

#             video_channel.send(data)

#             end = time.time()
#             print("max send framerate:", 1/(end-start))

#             await asyncio.sleep(1/frame_rate/5)
            
#     async def send_audio(audio_channel):
#         audio = pyaudio.PyAudio()
#         stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, input=True, frames_per_buffer=frames_per_buffer)

#         while True:
#             if not key_queue["audio"].empty():
#                 key["audio"] = await key_queue["audio"].get()

#             data = stream.read(frames_per_buffer, exception_on_overflow=False)

#             if encryption is not None:
#                 data = encryption.encrypt(data, key["audio"])
#             audio_channel.send(data)
#             await asyncio.sleep(audio_wait)

#     @pc.on("datachannel")
#     def on_datachannel(channel: RTCDataChannel):
#         print("New Data Channel: " + channel.label)
#         # Video key channel
#         if channel.label == "video key":
#             key_channel = channel

#             @key_channel.on("message")
#             async def on_message(message):
#                 await key_queue["video"].put(message)

#         # Video data channel
#         elif channel.label == "video data":
#             video_channel = channel

#             inpipe = ffmpeg.input('pipe:')
#             output = ffmpeg.output(inpipe, 'pipe:', format='rawvideo', pix_fmt='rgb24')

#             @video_channel.on("message")
#             async def on_message(message):
#                 start = time.time()

#                 cv2.namedWindow("recv", cv2.WINDOW_NORMAL)
#                 cv2.resizeWindow("recv", display_shape[1], display_shape[0])
#                 if not key_queue["video"].empty():
#                     key["video"] = await key_queue["video"].get()

#                 data = message
#                 if encryption is not None:
#                     data = encryption.decrypt(data, key["video"])

#                 data = output.run(input=data, capture_stdout=True, quiet=True)[0]

#                 data = np.frombuffer(data, dtype=np.uint8).reshape(video_shape)

#                 cv2.imshow("recv", data)
#                 cv2.waitKey(1)

#                 end = time.time()
#                 print("max recv framerate:", 1/(end-start))

#         # Audio key channel
#         elif channel.label == "audio key":
#             key_channel = channel

#             @key_channel.on("message")
#             async def on_message(message):
#                 await key_queue["audio"].put(message)

#         # Audio data channel
#         elif channel.label == "audio data":
#             audio_channel = channel

#             audio = pyaudio.PyAudio()
#             stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, output=True, frames_per_buffer=frames_per_buffer)
#             stream.start_stream()

#             @audio_channel.on("message")
#             async def on_message(message):
#                 if not key_queue["audio"].empty():
#                     key["audio"] = await key_queue["audio"].get()

#                 data = message
#                 if encryption is not None:
#                     data = encryption.decrypt(data, key["audio"])
                
#                 stream.write(data, num_frames=frames_per_buffer, exception_on_underflow=False)

#     await signaling.connect()

#     print("Ready for signaling")

#     if role == "offer":
#         # send offer

#         # video key channel
#         video_key_channel = pc.createDataChannel("video key")
#         @video_key_channel.on("open")
#         async def on_open():
#             asyncio.ensure_future(send_keys(video_key_channel, key_queue["video"]))
#             pass

#         # video data channel
#         video_channel = pc.createDataChannel("video data")
#         @video_channel.on("open")
#         async def on_open():
#             asyncio.ensure_future(send_video(video_channel))

#         # audio key channel
#         audio_key_channel = pc.createDataChannel("audio key")
#         @audio_key_channel.on("open")
#         async def on_open():
#             asyncio.ensure_future(send_keys(audio_key_channel, key_queue["audio"]))
#             pass

#         # audio data channel
#         audio_channel = pc.createDataChannel("audio data")
#         @audio_channel.on("open")
#         async def on_open():
#             asyncio.ensure_future(send_audio(audio_channel))

#         await pc.setLocalDescription(await pc.createOffer())
#         await signaling.send(pc.localDescription)


#     # consume signaling
#     while True:
#         obj = await signaling.receive()

#         if isinstance(obj, RTCSessionDescription):
#             await pc.setRemoteDescription(obj)

#             if obj.type == "offer":
#                 # send answer

#                 # video_channel = pc.createDataChannel(track.kind + " data")
#                 # @video_channel.on("open")
#                 # async def on_open():
#                 #     asyncio.ensure_future(send_video())
                    
#                 # add_tracks()
#                 await pc.setLocalDescription(await pc.createAnswer())
#                 await signaling.send(pc.localDescription)
#         elif isinstance(obj, RTCIceCandidate):
#             await pc.addIceCandidate(obj)
#         elif obj is BYE:
#             print("Exiting")
#             break

#         await pc.getStats()

# if __name__ == "__main__":

#     parser = argparse.ArgumentParser(description="Video stream from the command line")
#     parser.add_argument("role", choices=["offer", "answer"])
#     parser.add_argument("--verbose", "-v", action="count")
    
#     args = parser.parse_args()
#     if args.verbose:
#         logging.basicConfig(level=logging.DEBUG)

#     # Create signaling
#     HOST = '127.0.0.1'
#     # HOST = '100.80.231.89'
#     # HOST = '192.168.68.72'
#     # HOST = '128.54.191.80'
#     # HOST = '100.115.52.50'
#     # HOST = '0.0.0.0'
#     # HOST = '100.80.231.1'
#     PORT = '65431'
#     signaling_parser = argparse.ArgumentParser()
#     add_signaling_arguments(signaling_parser)
#     signaling_args = signaling_parser.parse_args(
#         ['--signaling', 'tcp-socket', '--signaling-host', HOST, '--signaling-port', PORT]
#     )
#     signaling = create_signaling(signaling_args)
#     pc = RTCPeerConnection()

#     encryption = EncryptionFactory().create_encryption_scheme("AES")

#     # Run event loop
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     try:
#         loop.run_until_complete( 
#             run(
#                 pc=pc,
#                 signaling=signaling,
#                 role=args.role,
#                 encryption=encryption,
#             )
#         )
#     except KeyboardInterrupt:
#         pass
#     finally:
#         # cleanup
#         loop.run_until_complete(signaling.close())
#         loop.run_until_complete(pc.close())

#     print("exit")



from threading import Thread
import asyncio

def display_message(user_id, msg):
    print(f"({user_id}): {msg}")

#region --- Tests ---

from flask_socketio import SocketIO, send, emit
from flask_socketio.namespace import Namespace as FlaskNamespace
from utils import ClientState

class TestFlaskNamespace(FlaskNamespace):
    def __init__(self, namespace, cls):
        super().__init__(namespace)
        self.cls = cls
        self.namespace = namespace

    def on_connect(self):
        self.cls.logger.info(f"Socket connection established to endpoint {self.cls.endpoint} on namespace /test")

    def on_message(self, auth, msg):
        user_id, sess_token = auth
        user_id = user_id
        self.cls.logger.info(f"Received /test message from User {user_id}: '{msg}'")
        if not self.cls.verify_sess_token(*auth):
            self.cls.logger.info(f"Authentication failed for User {user_id} with token '{sess_token}' at on_message.")
            return

        send((user_id,msg), broadcast=True)

    def on_disconnect(self):
        self.cls.logger.info(f"Client disconnected.")
        if self.cls.client.state == ClientState.CONNECTED:
            self.cls.client.state = ClientState.LIVE



from socketio import ClientNamespace

class TestClientNamespace(ClientNamespace):

    def __init__(self, namespace, cls):
        super().__init__(namespace)
        self.cls = cls

    def on_connect(self):
        self.cls.logger.info(f"Socket connection established to endpoint {self.cls.endpoint} on namespace /test")

    def on_message(self,user_id, msg):
        msg = '/test: ' + msg
        self.cls.logger.info(f"Received /test message from user {user_id}: {msg}")
        display_message(user_id, msg)

#endregion



#region --- Key Distributions ---


#endregion



#region --- Audio ---



#endregion



#region --- Video ---



#endregion



#region --- Generators ---

namespaces = {
    '/test': (TestFlaskNamespace, TestClientNamespace),
    }

def generate_flask_namespace(cls):
    return {name: namespaces[name][0](name, cls) for name in namespaces}

def generate_client_namespace(cls):
    return {name: namespaces[name][1](name, cls) for name in namespaces}

#endregion