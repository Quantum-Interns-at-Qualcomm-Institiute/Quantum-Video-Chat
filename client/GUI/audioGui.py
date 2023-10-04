
# gui.py

import tkinter as tk
from tkinter import messagebox
import sounddevice as sd
from icebox.audio import Audio

class GUI:
  
    def __init__(self, toggle_audio_callback, set_delay_callback, set_input_device_callback, audio):
        self.root = tk.Tk()
        self.root.title("Speech Jammer")
        self.toggle_audio_callback = toggle_audio_callback
        self.audio = audio
        self.set_delay_callback = set_delay_callback
        self.set_input_device_callback = set_input_device_callback
        self.create_widgets()

    def create_widgets(self):
        self.toggle_button = tk.Button(self.root, text="Start", command=self.toggle_audio)
        self.toggle_button.pack()

        self.delay_label = tk.Label(self.root, text="Delay (ms):")
        self.delay_label.pack()

        self.delay_entry = tk.Entry(self.root)
        self.delay_entry.pack()

        self.set_delay_button = tk.Button(self.root, text="Set Delay", command=self.set_delay)
        self.set_delay_button.pack()

        self.input_device_label = tk.Label(self.root, text="Input Device:")
        self.input_device_label.pack()

        self.input_device_var = tk.StringVar(self.root)
        self.input_device_optionmenu = tk.OptionMenu(self.root, self.input_device_var, *sd.query_devices(), command=self.set_input_device)
        self.input_device_optionmenu.pack()
      
        self.output_device_label = tk.Label(self.root, text="Output Device:")
        self.output_device_label.pack()

        self.output_device_var = tk.StringVar(self.root)
        self.output_device_optionmenu = tk.OptionMenu(self.root, self.output_device_var, *sd.query_devices(), command=self.set_output_device)
        self.output_device_optionmenu.pack()

    def set_input_device(self, device):
        self.audio.set_input_device(device)
    
    def set_output_device(self, device):
        self.output_device = device     
        
    def toggle_audio(self):
        if self.toggle_button.cget("text") == "Start":
            self.toggle_button.config(text="Stop")
        else:
            self.toggle_button.config(text="Start")
        self.toggle_audio_callback()

    def set_delay(self):
        try:
            delay = int(self.delay_entry.get())            
            if delay < 0:
                raise ValueError
            self.set_delay_callback(delay)
        except ValueError:
            messagebox.showerror("Invalid delay", "Delay must be a non-negative integer")

    def run(self):
        self.root.mainloop()