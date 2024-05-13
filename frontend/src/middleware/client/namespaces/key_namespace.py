import asyncio
import logging
from threading import Thread

from .base_namespaces import AVClientNamespace

logging.basicConfig(filename='./src/middleware/logs/client.log',
                    level=logging.INFO,
                    format='[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s',
                    datefmt='%H:%M:%S')


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
