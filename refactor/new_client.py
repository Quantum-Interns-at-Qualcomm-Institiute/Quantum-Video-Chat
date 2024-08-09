import json
import signal
import sys
from asyncio import Event
from hashlib import sha256
from threading import Thread

import ffmpeg
import socketio
from cv2 import VideoCapture, resize
from eventlet import sleep


class VideoThread(Thread):
    """
    Manages internal (non-blocking) loop to repeatedly send frames by extending Thread.
    """

    def __init__(self, server_sio, frontend_sio, height, width, scale=1):
        super().__init__()
        self._stop_event = Event()
        self.server_sio: socketio.Client = server_sio
        self.frontend_sio: socketio.Client = frontend_sio
        self.cap = VideoCapture(0)
        self.framerate = 15
        self.height = height * scale
        self.width = width * scale
        self.inpipe = ffmpeg.input(
            filename='pipe:',
            format='rawvideo',
            pix_fmt='bgr24',
            s=f"{self.height}x{self.width}",
            r=self.framerate,
        )
        self.output = ffmpeg.output(
            self.inpipe, 'pipe:', vcodec='libx264', f='ismv',
            preset='ultrafast', tune='zerolatency')

    def capture_frame(self):
        ret, frame = self.cap.read()

        if not ret:
            print('Image capture failed')
            return None, None, None

        frame = resize(frame, dsize=(self.width, self.height))

        processed = self.output.run(input=frame.tobytes(), capture_stdout=True, quiet=True)[0]

        frame_hash = sha256(processed).hexdigest()

        return frame, processed, frame_hash

    def run(self):
        """
        Repeatedly sends frames per (specified) `interval`.
        Breaks when `_stop_event` is set (by `stop()`).

        emits:
        - frame: Frame data
        """

        interval = 10
        while not self._stop_event.is_set():
            frame, processed_frame, frame_hash = self.capture_frame()
            if frame is None:
                print("Frame capture failed")
            else:
                self.server_sio.emit("frame", data={'frame': processed_frame, 'hash': frame_hash, 'sender': None})
                self.frontend_sio.emit("frame", {"frame": frame, "self": True})  # TODO: if slow send processed frame and re-process own frame
            sleep(interval)
        print("Thread has stopped")

    def stop(self):
        """
        Sets `_stop_event` to break loop initiated by `run()`.
        """
        self._stop_event.set()
        print("Stop event set")


width = 640
height = 480
server_sio = socketio.Client()
frontend_sio = socketio.Client()
thread = VideoThread(server_sio, frontend_sio, height, width)


@server_sio.on('connect')
def server_on_connect():
    """
    On connection to server, start a `VideoThread` to send frames.
    """
    print("Connected to Server")


@server_sio.on('frame')
def server_on_frame(data):
    """
    On receipt of a frame, display the frame.

    TODO: Displaying the frame
    """
    print(data['sender'])
    if sha256(data['frame']).hexdigest() == data['hash']:
        if data['sender'] is None:
            print("I got a frame back from myself!")
        else:
            inpipe = ffmpeg.input('pipe:')
            output = ffmpeg.output(inpipe, 'pipe:', format='rawvideo', pix_fmt='rgba')
            processed_frame = output.run(input=data['frame'], capture_stdout=True, quiet=True)[0]
            # from PIL import Image
            # Image.frombytes(mode="RGBA", size=(width, height), data=processed_frame).show() # DEBUG
            frontend_sio.emit('frame', {'frame': processed_frame, 'self': False})


@server_sio.on('disconnect')
def server_on_disconnect():
    """
    Stops VideoThread, in case it has not already been stopped.

    TODO: I don't like this redundnacy where the VideoThread may be stopped twice
    if user quits with SIGINT.
    """
    print("Connection with server has been severed.")
    thread.stop()


@server_sio.on('room')
def server_on_join_room(room):
    print(f"Received room {room} from server, sending to frontend")
    frontend_sio.emit("room", room)
    print("Starting video thread")
    # thread.start()


@frontend_sio.on('connect')
def frontend_on_connect():
    print("Connected to Frontend")


@frontend_sio.on('disconnect')
def frontend_on_disconnect():
    print("Successfully disconnected from frontend socket")


@frontend_sio.on('room')
def frontend_on_join_room(room):
    print(f"Frontend requests {room if len(room) > 0 else "new room"}")
    server_sio.emit("room", room)


@frontend_sio.on('leave_room')
def frontend_on_leave_room():
    raise NotImplementedError


def safe_connect(sio, address, port, label, retries=10, wait=15):
    for retry in range(retries):
        try:
            sio.connect(f"http://{address}:{port}", wait=True)
            break
        except Exception:
            if retries - retry >= 0:
                print(f"Connection to {label} failed, trying again in {wait} seconds, {retries - retry} more time(s)")
                for i in range(1, wait + 1):
                    print(f"{i}")
                    sleep(1)
            else:
                print("Connection failed too many times, exiting gracefully")
                # TODO: figure out how to exit gracefully


if __name__ == '__main__':
    def signal_handler(sig, frame):
        """
        Stops `VideoThread`. Disconnects `server_sio` from server.

        NOTE: This function should only be called to handle a `SIGINT`
        """

        print()
        print("Disconnecting...")
        if server_sio.connected:
            server_sio.disconnect()
            print("Disconnected!")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    with open(file="client_config.json") as json_data:
        config = json.load(json_data)
        server_address = 'localhost' if 'server' not in config or 'address' not in config['server'] else config['server']['address']
        server_port = 7777 if 'server' not in config or 'port' not in config['server'] else config['server']['port']
        frontend_address = 'localhost' if 'frontend' not in config or 'address' not in config['frontend'] else config['frontend']['address']
        frontend_port = 5000 if 'frontend' not in config or 'port' not in config['frontend'] else config['frontend']['port']

    safe_connect(frontend_sio, frontend_address, frontend_port, 'frontend')
    safe_connect(server_sio, server_address, server_port, 'server')
    # for retry in range(MAX_RETRYS):
    #     try:
    #         server_sio.connect(f"http://{server_address}:{server_port}", wait=True)
    #         break
    #     except Exception:
    #         if MAX_RETRYS - retry >= 0:
    #             print(f"Connection failed, trying again in {WAIT} seconds, {MAX_RETRYS - retry} more time(s)")
    #             for i in range(1, WAIT + 1):
    #                 print(f"{i}")
    #                 sleep(1)
    #         else:
    #             print("Connection failed too many times, exiting gracefully")
    #     finally:
    #         try:
    #             frontend_sio.connect(f"http://{frontend_address}:{frontend_port}")
    #         except Exception:
    #             print("Frontend isn't responding yet")

    while server_sio.connected:
        sleep(1)
