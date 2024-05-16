import asyncio
import logging
from threading import Thread
import cv2
import ffmpeg
from PIL import Image

from .base_namespaces import AVClientNamespace

logging.basicConfig(filename='./src/middleware/logs/client.log',
                    level=logging.INFO,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')


class VideoClientNamespace(AVClientNamespace):

    def on_connect(self):
        super().on_connect()
        inpipe1 = ffmpeg.input('pipe:')
        self.output = ffmpeg.output(
            inpipe1, 'pipe:', format='rawvideo', pix_fmt='nv12')

        async def send_video():
            await asyncio.sleep(2)
            cap = cv2.VideoCapture(0)

            inpipe = ffmpeg.input(
                'pipe:',
                format='rawvideo',
                pix_fmt='nv12',
                s='{}x{}'.format(
                    self.av_controller.video_shape[1], self.av_controller.video_shape[0]),
                r=self.av_controller.frame_rate,
            )

            output = ffmpeg.output(
                inpipe, 'pipe:', vcodec='libx264', f='ismv',
                preset='ultrafast', tune='zerolatency')

            while True:
                key_idx, key = self.av_controller.keys[-self.av_controller.key_buffer_size]

                _, image = cap.read()
                image = cv2.resize(
                    image, (self.av_controller.video_shape[1], self.av_controller.video_shape[0]))
                data = image.tobytes()
                print(f"Pre-sending video frame with key index {key_idx}")

                data = output.run(
                    input=data, capture_stdout=True, quiet=True)[0]

                data = self.av_controller.encryption.encrypt(data, key)
                print(f"Sending video frame with key index {key_idx}")
                self.send(key_idx.to_bytes(4, 'big') + data)

                await asyncio.sleep(1 / self.av_controller.frame_rate / 5)

        Thread(target=asyncio.run, args=(send_video(),)).start()

    def on_message(self, user_id, msg):
        super().on_message(user_id, msg)

        async def handle_message():
            if user_id == self.client_socket.user_id:
                return

            key_idx = int.from_bytes(msg[:4], 'big')
            key = self.av_controller.keys[key_idx][1]

            data = self.av_controller.encryption.decrypt(msg[4:], key)

            # Data is now an ISMV format file in memory
            data = self.output.run(input=data, capture_stdout=True,
                                   quiet=True)[0]

            image = Image.frombytes(mode="YCbCr", size=(self.av_controller.video_shape[1], self.av_controller.video_shape[0]), data=data).convert('RGBA')
            data = image.tobytes()
            image.show()

            print(f"Sending frame of size {len(data)} to frontend")
            self.frontend_socket.emit('stream', data)

        asyncio.run(handle_message())
