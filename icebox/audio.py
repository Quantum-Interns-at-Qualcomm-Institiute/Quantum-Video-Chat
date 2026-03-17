
# audio.py

import sounddevice as sd
import numpy as np
import time as t

class Audio:
    def __init__(self, config):
        self.config = config
        self.is_recording = False
        self.input_device = None
        self.output_device = None
        self.in_stream = None
        self.out_stream = None

    def start_recording(self):
        self.is_recording = True
        self.in_stream = sd.InputStream(device=self.input_device, callback=self.audio_callback)
        self.out_stream = sd.OutputStream(device=self.output_device,samplerate=self.config.samplerate)

        # Initially write empty buffer audio to outputstream to delay playback of new writes
        self.out_stream.start()
        out_channels = self.out_stream.channels
        delay_buffer_len = self.config.samplerate * (self.config.delay / 1000.0)
        delay_buffer = np.zeros((int(delay_buffer_len),out_channels), dtype=np.float32)
        self.out_stream.write(delay_buffer)

        self.in_stream.start()

    def stop_recording(self):
        if self.in_stream is not None:
            self.in_stream.stop()
            self.in_stream.close()
        if self.out_stream is not None:
            self.out_stream.stop()
            self.out_stream.close()
        self.is_recording = False

    def audio_callback(self, indata, frames, time, status):
        self.out_stream.write(indata)

    def set_input_device(self, device):
        self.input_device = device
        
    def set_output_device(self, device):
        self.output_device = device