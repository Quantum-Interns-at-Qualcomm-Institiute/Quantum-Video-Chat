import asyncio
import logging
from threading import Thread
import pyaudio
from .base_namespaces import AVClientNamespace

logging.basicConfig(filename='./src/middleware/logs/client.log',
                    level=logging.INFO,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')


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
                key_idx, key = self.av.keys[-2]

                data = stream.read(self.av.frames_per_buffer,
                                   exception_on_overflow=False)

                if self.av.encryption is not None:
                    data = self.av.encryption.encrypt(data, key)
                self.send(key_idx.to_bytes(4, 'big') + data)
                await asyncio.sleep(self.av.audio_wait)

        Thread(target=asyncio.run, args=(send_audio(),)).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)

        async def handle_message():
            if user_id == self.cls.user_id:
                return

            key_idx = int.from_bytes(msg[:4], 'big')
            key = self.av.keys[key_idx][1]
            data = msg[4:]

            data = self.av.encryption.decrypt(data, key)
            self.stream.write(
                data, num_frames=self.av.frames_per_buffer,
                exception_on_underflow=False)

        asyncio.run(handle_message())
