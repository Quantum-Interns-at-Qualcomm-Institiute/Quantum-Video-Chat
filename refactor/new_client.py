import json
import signal
from asyncio import Event
from hashlib import sha256
from threading import Thread

import ffmpeg
import socketio
from cv2 import VideoCapture, resize
from eventlet import sleep

# from PIL import Image


def countdown(seconds):
    print(f"Waiting #{seconds} seconds...")
    for i in range(1, seconds + 1):
        print(f"{i}")
        sleep(1)


def hash(data):
    m = sha256()
    m.update(data)
    return m.hexdigest()


scale = 1
width = 640 * scale
height = 480 * scale


class VideoThread(Thread):
    """
    Manages internal (non-blocking) loop to repeatedly send frames by extending Thread.
    """

    def __init__(self, sio):
        super().__init__()
        self._stop_event = Event()
        self.sio: socketio.Client = sio
        self.cap = VideoCapture(0)
        self.framerate = 15
        self.inpipe = ffmpeg.input(
            filename='pipe:',
            format='rawvideo',
            pix_fmt='bgr24',
            s=f"{height}x{width}",
            r=self.framerate,
        )
        self.output = ffmpeg.output(
            self.inpipe, 'pipe:', vcodec='libx264', f='ismv',
            preset='ultrafast', tune='zerolatency')

    def capture_frame(self):
        ret, frame = self.cap.read()

        if not ret:
            print('Image capture failed')
            return None

        frame = resize(frame, dsize=(width, height))

        processed = self.output.run(input=frame.tobytes(), capture_stdout=True, quiet=True)[0]

        frame_hash = hash(processed)

        return {'frame': processed, 'hash': frame_hash, 'sender': None}

    def run(self):
        """
        Repeatedly sends frames per (specified) `interval`.
        Breaks when `_stop_event` is set (by `stop()`).

        emits:
        - frame: Frame data
        """

        interval = 10
        while not self._stop_event.is_set():
            frame = self.capture_frame()
            if frame is None:
                print("Frame capture failed")
            else:
                self.sio.emit("frame", data=frame)
            sleep(interval)
        print("Thread has stopped")

    def stop(self):
        """
        Sets `_stop_event` to break loop initiated by `run()`.
        """
        self._stop_event.set()
        print("Stop event set")


server_sio = socketio.Client()
thread = VideoThread(server_sio)


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


@server_sio.on('connect')
def on_connect():
    """
    On connection to server, start a `VideoThread` to send frames.
    """
    print("Connected to Server")
    thread.start()


@server_sio.on('frame')
def on_frame(data):
    """
    On receipt of a frame, display the frame.

    TODO: Displaying the frame
    """
    print(data['sender'])
    if hash(data['frame']) == data['hash']:
        if data['sender'] is None:
            print("I got a frame back from myself!")
        else:
            inpipe = ffmpeg.input('pipe:')
            output = ffmpeg.output(inpipe, 'pipe:', format='rawvideo', pix_fmt='rgba')
            processed_frame = output.run(input=data['frame'], capture_stdout=True, quiet=True)[0]
            # Image.frombytes(mode="RGBA", size=(width, height), data=processed_frame).show() # DEBUG


@server_sio.on('disconnect')
def disconnect():
    """
    Stops VideoThread, in case it has not already been stopped.

    TODO: I don't like this redundnacy where the VideoThread may be stopped twice
    if user quits with SIGINT.
    """
    print("Connection with server has been severed.")
    thread.stop()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)

    MAX_RETRYS = 10
    WAIT = 5
    CONFIG = "client_config.json"
    with open(file=CONFIG) as json_data:
        config = json.load(json_data)
        address = 'localhost' if 'address' not in config else config['address']
        port = 7777 if 'port' not in config else config['port']

    for retry in range(MAX_RETRYS):
        try:
            server_sio.connect(f"http://{address}:{port}", wait=True)
            break
        except Exception:
            if MAX_RETRYS - retry >= 0:
                print(f"Connection failed, trying again in {WAIT} seconds, {MAX_RETRYS - retry} more times")
                countdown(WAIT)
            else:
                print("Connection failed, exiting gracefully")

    while server_sio.connected:
        sleep(1)
