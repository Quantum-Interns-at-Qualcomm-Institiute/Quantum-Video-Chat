import asyncio
import logging
from threading import Thread
import cv2
import ffmpeg

from .base_namespaces import AVClientNamespace

logging.basicConfig(filename='./src/middleware/logs/client.log',
                    level=logging.INFO,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')


class VideoClientNamespace(AVClientNamespace):

    def on_connect(self):
        super().on_connect()
        inpipe1 = ffmpeg.input('pipe:')
        self.output = ffmpeg.output(inpipe1, 'pipe:', format='rawvideo', pix_fmt='rgba')

        async def send_video():
            await asyncio.sleep(2)
            cap = cv2.VideoCapture(0)
            width = 3 * self.av_controller.video_shape[1] // 2
            height = 3 * self.av_controller.video_shape[0] // 2

            inpipe = ffmpeg.input(
                'pipe:',
                format='rawvideo',
                pix_fmt='bgr24',
                s=f'{width}x{height}',
                r=self.av_controller.frame_rate,
            )

            output = ffmpeg.output(
                inpipe, 'pipe:', vcodec='libx264', f='ismv',
                preset='ultrafast', tune='zerolatency')

            while True:
                key_idx, key = self.av_controller.keys[-self.av_controller.key_buffer_size]

                _, image = cap.read()
                image = cv2.resize(image, (width, height))
                data = image.tobytes()
                print(f"Pre-sending video frame with key index {key_idx}")

                data = output.run(input=data, capture_stdout=True, quiet=False)[0]

                data = self.av_controller.encryption.encrypt(data, key)
                print(f"Sending video frame with key index {key_idx}")
                msg = {'frame': key_idx.to_bytes(4, 'big') + data, 'width': width, 'height': height}
                self.send(msg=msg)

                await asyncio.sleep(1 / self.av_controller.frame_rate / 5)

        Thread(target=asyncio.run, args=(send_video(),)).start()

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
