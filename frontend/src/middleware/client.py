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
        print("Video thread has stopped")

    def stop(self):
        """
        Sets `_stop_event` to break loop initiated by `run()`.
        """
        self._stop_event.set()
        print("Stop event set")


class AudioThread(Thread):
    def __init__(self, sio: socketio.Client):
        import pyaudio
        super.__init__()
        self._stop_event = Event()
        self.sample_rate = None
        self.channels = 1
        self.frames_per_buffer = None
        self.delay = None
        self.sio = sio
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=pyaudio.paInt16, channels=self.channels, rate=self.sample_rate, output=True, frames_per_buffer=self.frames_per_buffer)

    def run(self):
        self.stream.start_stream()

        while not self._stop_event.is_set():
            data = self.stream.read(self.frames_per_buffer, False)
            self.sio.emit('audio', {'audio': data})
            sleep(self.delay)
        print("Audio thread has stopped")

    def stop(self):
        self._stop_event.set()


width = 640
height = 480
server_sio = socketio.Client()
frontend_sio = socketio.Client()
thread = VideoThread(server_sio, frontend_sio, height, width)

# SERVER EVENT HANDLERS


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
    thread.start()

# FRONTEND EVENT HANDLERS


@frontend_sio.on('connect')
def frontend_on_connect():
    print("Connected to Frontend")


@frontend_sio.on('disconnect')
def frontend_on_disconnect():
    print("Successfully disconnected from frontend socket")


@frontend_sio.on('join-room')
def frontend_on_join_room(room=None):
    print(f"Frontend requests {room if room else "new room"}")
    server_sio.emit("room", room)


@frontend_sio.on('leave-room')
def frontend_on_leave_room():
    print("User wants to leave their room...")
    server_sio.emit("leave")

if __name__ == '__main__':
    # TODO: there's a better spot for this but we don't have a class they fit in
    def safe_connect(sio, address, port, label, retries=10, wait=15):
        """
        Repeatedly attempts to connect an arbitrary socket client to an arbitrary endpoint.
        Blocks until successful connection or until max retries exceeded.

        Parameters
        sio (socketio.Client): Client to use for connection
        address (str): 
        port (int): 
        label (str): Name of server; for logging
        retries (int): How many attempts to make before failure
        wait (int): Seconds to wait between retries
        """
        print(f"Attempting connection to {label}")
        for retry in range(retries):
            try:
                sio.connect(f"http://{address}:{port}", wait=True)
                break
            except Exception as e:
                print(e)
                if retries - retry >= 0:
                    print(f"Connection to {label} failed, trying again in {wait} seconds, {retries - retry} more time(s)")
                    for i in range(1, wait + 1):
                        print(f"{i}")
                        sleep(1)
                else:
                    print("Connection failed too many times, exiting gracefully")
                    # TODO: figure out how to exit gracefully

    def signal_handler(sig, frame):
        """
        Stops `VideoThread`. Disconnects `server_sio` from server.

        NOTE: This function should only be called to handle a `SIGINT`
        """

        print("\nDisconnecting...")
        if server_sio.connected:
            server_sio.disconnect()
            print("Disconnected!")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('port', help='Port to communicate with frontend (address is assumed to be \'localhost\')')
    args = parser.parse_args()

    frontend_address = 'localhost'
    frontend_port = args.port

    with open(file="src/middleware/client_config.json") as json_data:
        config = json.load(json_data)
        server_address = config['server']['address']
        server_port = config['server']['port']
        # server_address = 'localhost' if 'server' not in config or 'address' not in config['server'] else config['server']['address']
        # server_port = 7777 if 'server' not in config or 'port' not in config['server'] else config['server']['port']
        # frontend_address = 'localhost' if 'frontend' not in config or 'address' not in config['frontend'] else config['frontend']['address']
        # frontend_port = 5000 if 'frontend' not in config or 'port' not in config['frontend'] else config['frontend']['port']

    safe_connect(frontend_sio, frontend_address, frontend_port, 'frontend')
    safe_connect(server_sio, server_address, server_port, 'server')

    # Send 'ready' event to frontend when connected to both frontend and server
    print('Ready to start chatting.')
    frontend_sio.emit('ready')

    while server_sio.connected:
        sleep(seconds=1)
