# import time
# # import numpy as np
# # import io
# # from PIL import Image
# import argparse
# # import io
# from asyncio import Event
# import signal
# from threading import Thread
# import socketio
# import sys
# import psutil
# import eventlet
# import PIL
# import cv2


# def start_server(ipaddress, port):

#     sio = socketio.Server()
#     app = socketio.WSGIApp(sio)

#     @sio.on('connect')
#     def connect(sid, environ):
#         t = time.localtime()
#
#         print(f'Connected by socket at {current_time}')

#     @sio.on('frame')
#     def frame(sid, data):
#         t = time.localtime()
#
#         print(f'I got a frame at {current_time}')
#         sio.emit('frame', data)
#         print('Right back atcha!')

#     @sio.on('disconnect')
#     def disconnect(sid):
#         t = time.localtime()
#
#         print(f'Socket disconnected at {current_time}')

#     eventlet.wsgi.server(eventlet.listen((ipaddress, port)), app)


# def start_client(ipaddress, port, interval):
#     sio = socketio.Client()

#     class CaptureThread(Thread):
#         def __init__(self):
#             super().__init__()
#             self._stop_event = Event()

# def run(self):
#     cap = cv2.VideoCapture(0)  # assuming your camera is at index 0, change it as per need

#     while not self._stop_event.is_set():
#         print("Say 'cheese'!")
#         ret, frame = cap.read()

#         if not ret:
#             print("Failed to capture image")
#             continue

#         # is_success, im_buf_arr = cv2.imencode(".jpg", frame)
#         # byte_im = io.BytesIO(im_buf_arr)
#         # image = Image.open(byte_im)

#         sio.emit('frame', frame.tobytes())  # emit 'frame' event with encoded image data
#         t = time.localtime()

#         print(f"Sent a frame out at {current_time}")
#         time.sleep(interval)

#     cap.release

#     capture_thread = CaptureThread()

#     @sio.on('connect')
#     def connect():
#         t = time.localtime()
#
#         print(f"Connect server response at {current_time}")
#         print('Connected to server')
#         capture_thread.start()
#         print('Background task started!')

#     @sio.on('disconnect')
#     def disconnect():
#         t = time.localtime()
#
#         print(f"Disconnect server response at {current_time}")
#         print('disconnected from server')

#     @sio.on('frame')
#     def frame_returned(frame):
#         t = time.localtime()
#
#         print(f"Frame server response at {current_time}")
#         print('I got a frame back:')
#         # byte_im = base64.b64decode(b64_im)
#         _ = PIL.Image.open(frame.frombytes())

#     def signal_handler(sig, frame):
#         print('')
#         print('Stopping thread...')
#         capture_thread.stop()
#         print('Disconnecting...')
#         if sio is not None:
#             sio.disconnect()  # disconnect from the server when ctrl+c is pressed
#         print('Exiting!')
#         sys.exit(0)

#     signal.signal(signal.SIGINT, signal_handler)  # Ctrl+c leads to a clean teardown

#     sio.connect(f'http://{ipaddress}:{port}', namespaces='/')
#     sio.wait()

import argparse
from asyncio import Event
import hashlib
import signal
from threading import Thread
from datetime import datetime
from PIL import Image
import cv2
import ffmpeg
import socketio
import sys
import psutil
import eventlet


def right_now():
    return datetime.now().strftime("%H:%M:%S.%f")


def get_hash(data):
    m = hashlib.sha256()
    m.update(data)
    return m.hexdigest()


def start_server(ipaddress, port):

    sio = socketio.Server()
    app = socketio.WSGIApp(sio)

    @sio.on('connect')
    def connect(sid, environ):
        print(f'Connected by socket at {right_now()}')

    @sio.on('send_frame')
    def send_frame(sid, data):
        print(f'I was sent frame #{data['count']} at {right_now()}')
        sio.emit('ret_frame', data)
        print('So I sent it right back!')

    @sio.on('disconnect')
    def disconnect(sid):
        print(f'Socket disconnected at {right_now()}')

    eventlet.wsgi.server(eventlet.listen((ipaddress, port)), app)


def start_client(ipaddress, port, interval):

    class ClientThread(Thread):
        def __init__(self, sio):
            super().__init__()
            self.sio: socketio.Client = sio
            self._stop_event = Event()
            self.cap = cv2.VideoCapture(0)

        def run(self):
            eventlet.sleep(interval)
            count = 0
            LENGTH = 640
            WIDTH = 480
            FRAMERATE = 15

            inpipe = ffmpeg.input(
                filename='pipe:',
                format='rawvideo',
                pix_fmt='nv12',
                s=f'{LENGTH}x{WIDTH}',
                r=FRAMERATE,
            )
            output = ffmpeg.output(
                inpipe, 'pipe:', vcodec='libx264', f='ismv',
                preset='ultrafast', tune='zerolatency')

            while not self._stop_event.is_set():
                print(f"Starting image processing at {right_now()}")
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to capture image")
                    continue

                count += 1
                image = cv2.resize(frame, (LENGTH, WIDTH))
                processed = output.run(
                    input=image.tobytes(), capture_stdout=True, quiet=True)[0]

                print(f"Frame #{count} processing completed at {right_now()}! Sending...")
                self.sio.emit('send_frame', data={
                    'count': count,
                    'frame': processed,
                    'hash': get_hash(processed)
                })  # emit 'send_frame' event
                eventlet.sleep(interval)

        def stop(self):
            self._stop_event.set()
            self.cap.release()

    def signal_handler(sig, frame):
        print('')
        print(f'You pressed Ctrl+C! Stopping thread at {right_now()}...')
        client_thread.stop()
        print('Disconnecting...')
        if sio is not None:
            sio.disconnect()
        print('Exiting!')
        sys.exit(0)

    sio = socketio.Client()
    client_thread = ClientThread(sio)

    @sio.on('connect')
    def connect():
        print(f'Connected to server at {right_now()}')
        client_thread.start()
        print(f'Thread started at {right_now()}!')

    @sio.on('disconnect')
    def disconnect():
        print(f'Disconnected from server at {right_now()}')

    @sio.on('ret_frame')
    def ret_frame(data):
        unmodified = get_hash(data['frame']) == data['hash']
        print(f'I received {'an unmodified' if unmodified else 'modified'} frame #{data['count']} at {right_now()}!')
        if unmodified:
            inpipe1 = ffmpeg.input('pipe:')
            output = ffmpeg.output(inpipe1, 'pipe:', format='rawvideo', pix_fmt='nv12')
            processed = output.run(input=data['frame'], capture_stdout=True, quiet=True)[0]
            image = Image.frombytes(mode="YCbCr", size=(640, 480), data=processed).convert('RGBA')
            image.show()

    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+c leads to a clean teardown

    sio.connect(f'http://{ipaddress}:{port}', namespaces='/')
    sio.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    addr_group = parser.add_mutually_exclusive_group(required=True)
    addr_group.add_argument('-i', '--ipaddress', help="IP address to bind to")
    addr_group.add_argument('-n', '--interface', type=str, help="Interface name to bind to")

    parser.add_argument('-p', '--port', type=int, required=True, help="Port number to listen on/connect to")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('-s', '--server', action='store_true', help="Start server mode")
    mode_group.add_argument('-c', '--client', action='store_true', help="Start client mode")

    parser.add_argument('--interval', type=float, default=5, help='Interval between pings in seconds (default: 5)')

    args = parser.parse_args()

    if args.interface:
        ip = psutil.net_if_addrs()[args.interface][0].address if args.interface in args.interface else None
        if not ip:
            print(f"Error: Invalid interface name {args.interface}")
            sys.exit(1)
    else:
        ip = args.ipaddress

    if args.server:
        start_server(ip, args.port)
    elif args.client:
        start_client(ip, args.port, args.interval)
