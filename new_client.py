import signal
from asyncio import Event
from threading import Thread

import socketio
from eventlet import sleep


class VideoThread(Thread):
    def __init__(self, sio):
        super().__init__()
        self._stop_event = Event()
        self.sio: socketio.Client = sio

    def run(self):
        interval = 1
        sleep(interval)
        while not self._stop_event.is_set():
            print("sending...")
            self.sio.emit("frame", data={'frame': 'value'})
            sleep(interval)
        print("Thread has stopped")

    def stop(self):
        self._stop_event.set()
        print("Stop event set")


server_sio = socketio.Client()
thread = VideoThread(server_sio)


def signal_handler(sig, frame):
    print()
    print("Disconnecting...")
    if server_sio.connected:
        server_sio.disconnect()
        print("Disconnected!")


def countdown(seconds):
    print(f"Waiting #{seconds} seconds...")
    for i in range(1, seconds + 1):
        print(f"{i}...")
        sleep(1)


@server_sio.on('connect')
def connect():
    print("Connected to Server")
    thread.start()


@server_sio.on('frame')
def ping(data):
    print(f"I got a frame from {data['sid']}!")


@server_sio.on('disconnect')
def disconnect():
    print("Server disconnected, shutting down")
    thread.stop()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)

    MAX_RETRYS = 10
    WAIT = 5

    for retry in range(MAX_RETRYS):
        try:
            server_sio.connect("http://127.0.0.1:4334", wait=True)
            break
        except Exception:
            if MAX_RETRYS - retry >= 0:
                print(f"Connection failed, trying again in {WAIT} seconds, {MAX_RETRYS - retry} more times")
                countdown(WAIT)
            else:
                print("Connection failed, exiting gracefully")

    while server_sio.connected:
        sleep(1)
