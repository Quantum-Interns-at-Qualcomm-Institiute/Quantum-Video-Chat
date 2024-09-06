import tkinter as tk
from asyncio import Event
from random import choices
from string import ascii_lowercase

# from hashlib import sha256
from threading import Thread

import ffmpeg
import socketio
from cv2 import COLOR_BGR2RGBA, VideoCapture, cvtColor, resize
from eventlet import sleep
from PIL import Image, ImageTk

global _thread
_thread = None
global _thread_
global made_self


class App(tk.Tk):
    def call_to_start(self):
        self.showFrame(self.start_frame)
        # raise NotImplementedError

    def join_to_start(self):
        self.showFrame(self.start_frame)
        # raise NotImplementedError

    def any_to_call(self, id=None):
        if id is None:
            id = ''.join(choices(ascii_lowercase, k=5))
        print(id)
        self.showFrame(self.call_frame)

    def __init__(self):
        super().__init__()

        self.title("Multi-Screen App")
        self.geometry('1080x720')

        # Create two frames
        self.start_frame = tk.Frame(self)
        self.join_frame = tk.Frame(self)
        self.call_frame = tk.Frame(self)

        # Hide all frames initially
        self.hideAllFrames()

        # Create widgets for frame 1
        btnStart = tk.Button(self.start_frame, text="Start", command=lambda: self.any_to_call())
        btnJoin = tk.Button(self.start_frame, text="Join", command=lambda: self.showFrame(self.join_frame))

        # Position widgets for frame 1
        btnStart.place(relx=0.5, rely=0.4, anchor=tk.CENTER)
        btnJoin.place(relx=0.5, rely=0.6, anchor=tk.CENTER)

        # Create widgets for frame 2
        self.entryID = tk.Entry(self.join_frame)
        btnJoin2 = tk.Button(self.join_frame, text="Join", command=lambda: self.any_to_call(self.entryID.get()))
        btnBack = tk.Button(self.join_frame, text="Back", command=lambda: self.join_to_start())

        # Position widgets for frame 2
        self.entryID.place(relx=0.5, rely=0.4, anchor=tk.CENTER)
        self.entryID.focus()
        btnJoin2.place(relx=0.5, rely=0.6, anchor=tk.CENTER)
        btnBack.place(relx=1.0, rely=1.0, anchor=tk.SE)

        # Create widgets for frame 3
        self.me_panel = tk.Label(self.call_frame)
        self.them_panel = tk.Label(self.call_frame)
        btnBack = tk.Button(self.call_frame, text="Back", command=lambda: self.call_to_start())
        btnBack.place(relx=1.0, rely=1.0, anchor=tk.SE)

        self.me_panel.place(relx=0.25, rely=0.4, anchor=tk.CENTER)
        self.them_panel.place(relx=0.75, rely=0.4, anchor=tk.CENTER)

        # Show first frame initially
        self.showFrame(self.start_frame)

    def hideAllFrames(self):
        for frame in [self.start_frame, self.join_frame, self.call_frame]:
            frame.place_forget()

    def showFrame(self, frame):
        self.hideAllFrames()  # Hide all frames before showing the selected one
        if frame == self.call_frame:
            try:
                _thread = VideoThread(None, None, 480, 640, self.me_panel)
                _thread.start()
            except Exception as e:
                print("Error starting video capture: ", str(e))
        elif frame == self.start_frame:
            try:
                _thread.stop()
                _thread = None
            except:
                pass

        frame.place(relx=0, rely=0, relwidth=1, relheight=1)  # Show the selected frame

    def videoLoop(self, panel):
        _, frame = self.video.read()

        if frame is not None:
            frame_resized = resize(frame, (600, 440))
            image = cvtColor(frame_resized, COLOR_BGR2RGBA)  # Convert from BGR to RGB
            self.image = ImageTk.PhotoImage(Image.fromarray(image))
            panel.config(image=self.image)

        sleep(1)
        self.videoLoop(panel)  # call this function again after 15 ms (~60 FPS)

    def startVideoCapture(self):
        self.video = VideoCapture(0)

        if not self.video.isOpened():
            print('Error opening video camera')

        else:
            Thread(target=self.videoLoop(self.me_panel)).start()
            # sleep(5)
            # Thread(target=self.videoLoop(self.them_panel)).start()


class VideoThread(Thread):
    """
    Manages internal (non-blocking) loop to repeatedly send frames by extending Thread.
    """

    def __init__(self, server_sio, frontend_sio, height, width, panel, scale=1, delay=0):
        super().__init__()
        self._stop_event = Event()
        self.server_sio: socketio.Client = server_sio
        self.frontend_sio: socketio.Client = frontend_sio
        self.cap = VideoCapture(0)
        self.framerate = 15
        self.height = height * scale
        self.width = width * scale
        self.panel = panel
        self.delay = delay
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
        """
        Captures a single frame of video at the set resolution

        Returns:
            raw_frame, processed_frame: capture from the user's camera
            - raw_frame (bytes): 640x480 bgr24 formatted image
            - processed_frame (bytes): 640x480 ismv fomatted h264 video frame
        """
        ret, frame = self.cap.read()

        if not ret:
            print('Image capture failed')
            return None, None, None

        # frame = resize(frame, dsize=(self.width, self.height))

        processed = self.output.run(input=frame.tobytes(), capture_stdout=True, quiet=True)[0]

        return frame, processed

    def start(self):
        print("Starting video thread")
        super().start()

    def run(self):
        """
        Repeatedly sends frames per (specified) `interval`.
        Breaks when `_stop_event` is set (by `stop()`).

        emits:
        - frame: Frame data
        """

        interval = 1 / 30
        # sleep(self.delay)
        while not self._stop_event.is_set():
            frame, processed_frame = self.capture_frame()
            if frame is None:
                print("Frame capture failed")
            else:
                frame_resized = resize(frame, (self.width, self.height))
                image = cvtColor(frame_resized, COLOR_BGR2RGBA)  # Convert from BGR to RGB
                img = ImageTk.PhotoImage(Image.fromarray(image))
                self.panel.config(image=img)
            sleep(interval)
        print("Video thread has stopped")

    def stop(self):
        """
        Sets `_stop_event` to break loop initiated by `run()`.
        """
        self._stop_event.set()
        print("Stop event set")


app = App()
app.mainloop()

while True:
    sleep(1)
