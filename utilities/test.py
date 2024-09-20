import json
import tkinter as tk
from asyncio import Event
from hashlib import sha256
from random import choices
from string import ascii_lowercase
from threading import Thread

import ffmpeg
import numpy as np
import socketio
from cv2 import COLOR_BGR2RGBA, VideoCapture, cvtColor, resize
from eventlet import sleep
from PIL import Image, ImageTk


class App(tk.Tk):
    def safe_connect(self, sio: socketio.Client, address, port, label, retries=10, wait=15):
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

    def call_to_start(self):
        '''
        Function called when the back button is pressed on the "call" screen

        TODO:
            stop video thread
            disconnect from server
        '''
        print("User wants to leave room")
        self.video_thread.stop()
        self.sio.emit('leave-room')
        self.start_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

    def any_to_call(self):
        '''
        Function called when "join" button is pressed on the "start" or "join" screens

        TODO:
            send server call
        '''
        id = self.id_var.get() if self.id_var.get() != '' else None
        print(f"Sending join request with id: {id}.")
        self.server_sio.call('join-room', id)

        # Listen for server response with room-id

    def __init__(self):
        '''
        Initializes the app
        '''
        super().__init__()

        with open(file="client_config.json") as json_data:
            config = json.load(json_data)
            self.server_address = 'localhost' if 'address' not in config else config['address']
            self.server_port = 7777 if 'port' not in config else config['port']

        self.title("Multi-Screen App")
        self.geometry('1080x720')

        self.room_id = None

        # Create two frames
        self.start_frame = tk.Frame(self)
        self.join_frame = tk.Frame(self)
        self.call_frame = tk.Frame(self)
        self.video_thread = None

        # Hide all frames initially
        self.hideAllFrames()

        # Create widgets for start frame
        self.id_var = tk.StringVar()
        btnStart = tk.Button(self.start_frame, text="Start", command=lambda: self.any_to_call())
        btnJoin = tk.Button(self.start_frame, text="Join", command=lambda: self.any_to_call())
        txtJoin = tk.Entry(self.start_frame, textvariable=self.id_var)

        # Position widgets for start frame 
        btnStart.place(relx=0.5, rely=0.4, anchor=tk.CENTER)
        btnJoin.place(relx=0.5, rely=0.6, anchor=tk.CENTER)
        txtJoin.place(relx=0.5, rely=0.55, anchor=tk.CENTER)
        txtJoin.focus()

        # Create widgets for call frame
        self.me_panel = tk.Label(self.call_frame)
        self.them_panel = tk.Label(self.call_frame)
        btnBack = tk.Button(self.call_frame, text="Back", command=lambda: self.call_to_start())
        btnBack.place(relx=1.0, rely=1.0, anchor=tk.SE)

        self.me_panel.place(relx=0.25, rely=0.4, anchor=tk.CENTER)
        self.them_panel.place(relx=0.75, rely=0.4, anchor=tk.CENTER)

        # Show start frame initially
        self.start_frame.place(relx=0, rely=0, relwidth=1, relheight=1)


        # Init Socket
        self.server_sio = socketio.Client()
        self.safe_connect(self.server_sio, self.server_address, self.server_port, 'server')

        # Listen for room id from server
        def on_room_id(id):
            print(f"Server assigned id {id}")
            self.room_id = id
            self.call_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.video_thread = VideoThread(self.server_sio, 480, 640, self.me_panel, self.them_panel)
            self.video_thread.start()
        self.server_sio.on('room-id', on_room_id)

        def on_frame(frame_data):
            if sha256(frame_data['frame']).hexdigest() == frame_data['hash']:
                inpipe = ffmpeg.input('pipe:')
                output = ffmpeg.output(inpipe, 'pipe:', format='rawvideo', pix_fmt='rgba')
                new_processed_frame = output.run(input=frame_data['frame'], capture_stdout=True, quiet=True)[0]
                image = Image.frombytes('RGBA', (640, 480), new_processed_frame)
                tk_image = ImageTk.PhotoImage(image)

                self.them_panel.config(image=tk_image)
                # self.them_panel
            else:
                print("hash mismatch on frame")
        self.server_sio.on('frame', on_frame)

    def hideAllFrames(self):
        for frame in [self.start_frame, self.join_frame, self.call_frame]:
            frame.place_forget()

class VideoThread(Thread):
    """
    Manages internal (non-blocking) loop to repeatedly send frames by extending Thread.
    """

    def __init__(self, server_sio, height, width, panel, them_panel, scale=1):
        super().__init__()
        self._stop_event = Event()
        self.server_sio: socketio.Client = server_sio
        self.cap = VideoCapture(0)
        self.framerate = 15
        self.height = height * scale
        self.width = width * scale
        self.panel = panel
        self.them_panel = them_panel
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
        
        resized_frame = resize(frame, (self.width, self.height))

        processed = self.output.run(input=resized_frame.tobytes(), capture_stdout=True, quiet=True)[0]

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

        interval = 1/10
        while not self._stop_event.is_set():
            frame, processed_frame = self.capture_frame()
            
            if frame is None:
                print("Frame capture failed")
            else:
                resized_frame = resize(frame, (self.width, self.height))
                color_corrected_frame = cvtColor(resized_frame, COLOR_BGR2RGBA)
                image = Image.fromarray(color_corrected_frame)
                img = ImageTk.PhotoImage(image)
                self.panel.config(image=img)
                # self.them_panel.config(image=img)
                self.server_sio.emit("frame", data={'frame': processed_frame, 'hash': sha256(processed_frame).hexdigest(), 'sender': None})


                # inpipe = ffmpeg.input('pipe:')
                # output = ffmpeg.output(inpipe, 'pipe:', format='rawvideo', pix_fmt='rgba')
                # new_processed_frame = output.run(input=processed_frame, capture_stdout=True, quiet=True)[0]
                # image = Image.frombytes('RGBA', (640, 480), new_processed_frame)
                # tk_image = ImageTk.PhotoImage(image)
                
                # self.them_panel.config(image=tk_image)


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