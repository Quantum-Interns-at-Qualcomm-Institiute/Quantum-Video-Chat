import argparse
from asyncio import Event
import hashlib
import signal
from threading import Thread
from datetime import datetime
import cv2
import ffmpeg
import socketio
import sys
import psutil
import eventlet
from time import sleep


def right_now():
    return datetime.now().strftime('%H:%M:%S.%f')


def get_hash(data):
    m = hashlib.sha256()
    m.update(data)
    return m.hexdigest()


def start_server(ipaddress, port):

    sio = socketio.Server()
    app = socketio.WSGIApp(sio)

    @sio.on('connect')
    def connect(sid, environ):
        print(f"Connected by socket at {right_now()}")

    @sio.on('send_frame')
    def send_frame(sid, data):
        print(f"I was sent frame #{data['count']} at {right_now()}")
        sio.emit('ret_frame', data)
        print('So I sent it right back!')

    @sio.on('disconnect')
    def disconnect(sid):
        print(f"Socket disconnected at {right_now()}")

    eventlet.wsgi.server(eventlet.listen((ipaddress, port)), app)


def start_client(ipaddress, port, interval, width, height, frontend_port):
    frontend_enabled = frontend_port > 0
    width = 3 * width // 2
    height = 3 * height // 2

    class ClientThread(Thread):
        def __init__(self, sio):
            super().__init__()
            self.sio: socketio.Client = sio
            self._stop_event = Event()
            self.cap = cv2.VideoCapture(0)
            self.framerate = 15

        def send_frame(self, count):
            print(f"[send] Starting image processing at {right_now()}")
            ret, frame = self.cap.read()  # Pixels are represented in BGR format (Blue, Green, Red) by default in OpenCV

            if not ret:
                print('Failed to capture image')
                return

            frame = cv2.resize(frame, dsize=(width, height))

            inpipe = ffmpeg.input(
                filename='pipe:',
                format='rawvideo',
                pix_fmt='bgr24',
                s=f"{height}x{width}",
                r=self.framerate,
            )

            output = ffmpeg.output(
                inpipe, 'pipe:', vcodec='libx264', f='ismv',
                preset='ultrafast', tune='zerolatency')

            processed = output.run(
                input=frame.tobytes(), capture_stdout=True, quiet=True)[0]

            print(f"[send] Frame #{count} processing completed at {right_now()}! Sending...")
            self.sio.emit('send_frame', data={
                'count': count,
                'frame': processed,
                'hash': get_hash(processed)
            })  # emit 'send_frame' event

        def run(self):
            count = 0
            eventlet.sleep(interval)

            while not self._stop_event.is_set():
                count += 1
                self.send_frame(count)
                eventlet.sleep(interval)

        def stop(self):
            self._stop_event.set()
            self.cap.release()

    def signal_handler(sig, frame):
        print('')
        print(f"You pressed Ctrl+C! Stopping thread at {right_now()}...")
        client_thread.stop()
        print('Disconnecting...')
        if server_sio is not None:
            server_sio.disconnect()
        if frontend_sio is not None:
            frontend_sio.disconnect()
        print('Exiting!')
        sys.exit(0)

    server_sio = socketio.Client()
    frontend_sio = socketio.Client()
    client_thread = ClientThread(server_sio)

    @server_sio.on('connect')
    def connect():
        print(f"Connected to server at {right_now()}")
        client_thread.start()
        print(f"Thread started at {right_now()}!")
        if frontend_enabled:
            frontend_sio.connect(f"http://localhost:{frontend_port}", namespaces='/')

    @server_sio.on('disconnect')
    def disconnect():
        print(f"Disconnected from server at {right_now()}")

    @server_sio.on('ret_frame')
    def ret_frame(data):
        unmodified = get_hash(data['frame']) == data['hash']
        print(f"I received {'an unmodified' if unmodified else 'modified'} frame #{data['count']} at {right_now()}!")
        if unmodified:
            print(f"[receive] Starting image processing at {right_now()}")
            inpipe = ffmpeg.input('pipe:')
            output = ffmpeg.output(inpipe, 'pipe:', format='rawvideo', pix_fmt='rgba')
            processed_frame = output.run(input=data['frame'], capture_stdout=True, quiet=True)[0]

            if frontend_enabled:
                frontend_sio.emit('stream', data={
                    'count': data['count'],
                    'frame': processed_frame,
                    'width': width,
                    'height': height
                })

    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+c leads to a clean teardown
    MAX_RETRYS = 5
    WAIT = 10
    for retry in range(MAX_RETRYS):
        try:
            server_sio.connect(f"http://{ipaddress}:{port}", namespaces='/', wait=True)
            break
        except Exception:
            if MAX_RETRYS - retry >= 0:
                print(f"Connection failed, trying again in {WAIT} seconds, {MAX_RETRYS - retry} more times")
                sleep(WAIT)
            else:
                print("Connection failed, exiting gracefully")

    server_sio.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # Required
    required = parser.add_argument_group('Required')
    mode_group = required.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('-s', '--server', action='store_true', help='Host a bouncer server')
    mode_group.add_argument('-c', '--client', action='store_true', help='Connect to a pre-existing server')

    addr_group = required.add_mutually_exclusive_group(required=True)
    addr_group.add_argument('-i', '--ipaddress', type=str, help='IP address to bind/connect to')
    addr_group.add_argument('-n', '--interface', type=str, help='Interface name to bind/connect to')

    required.add_argument('-p', '--port', type=int, required=True, help='Port number to listen on/connect to')

    # Optional
    optional = parser.add_argument_group('Client Options', 'These only affect the program when run in client mode')
    optional.add_argument('--interval', type=float, default=5, help='Interval between frames in seconds (default: %(default)ss)')
    optional.add_argument('--width', type=int, default=640, help='Desired horizontal size of the frame (default: %(default)spx)')
    optional.add_argument('--height', type=int, default=480, help='Desired vertical size of the frame (default: %(default)spx)')
    optional.add_argument('--frontend', type=int, default=-1, help='Frontend port data is sent to. (default: no frontend)')

    args = parser.parse_args()

    if args.interface:
        ip = psutil.net_if_addrs()[args.interface][0].address if args.interface in args.interface else None
        if not ip:
            print("Error: Invalid interface name {args.interface}")
            sys.exit(1)
    else:
        ip = args.ipaddress

    if args.server:
        start_server(ip, args.port)
    elif args.client:
        start_client(ip, args.port, args.interval, args.width, args.height, args.frontend)
