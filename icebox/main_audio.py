
# main.py
import logging
import tkinter as tk
from tkinter import messagebox
from client.GUI.gui import GUI
from icebox.audio import Audio
from icebox.audio_config import Config

logging.basicConfig(level=logging.INFO)

class Main:
    def __init__(self):
      config_file = None
      self.config = Config(config_file)
      self.audio = Audio(self.config)
      self.gui = GUI(self.toggle_audio, self.set_delay, self.set_input_device, self.audio)

    def toggle_audio(self):
        if self.audio.is_recording:
            self.audio.stop_recording()
        else:
            self.audio.start_recording()
            
    def set_input_device(self, device):
      self.audio.set_input_device(device)

    def set_delay(self, delay):
        try:
            delay = int(delay)
            if delay < 0 or delay > 10000:
                raise ValueError
            self.config.set_delay(delay)
        except ValueError:
            logging.error(f"Tried to set an invalid delay of {delay} ms")
            messagebox.showerror("Invalid delay", "Delay must be within the range 0 to 10000")
            

    def run(self):
        self.gui.run()

if __name__ == "__main__":
    main = Main()
    main.run()

