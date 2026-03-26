"""Main entry point for the audio GUI application."""

import logging
from tkinter import messagebox

from client.GUI.audioGui import GUI

from icebox.audio import Audio
from icebox.audio_config import Config

logger = logging.getLogger(__name__)

# Audio delay validation bound
_MAX_DELAY_MS = 10000


class Main:
    """Application controller for audio recording with GUI."""

    def __init__(self):
        """Initialize audio config, audio engine, and GUI."""
        config_file = None
        self.config = Config(config_file)
        self.audio = Audio(self.config)
        self.gui = GUI(self.toggle_audio, self.set_delay, self.set_input_device, self.audio)

    def toggle_audio(self):
        """Toggle audio recording on or off."""
        if self.audio.is_recording:
            self.audio.stop_recording()
        else:
            self.audio.start_recording()

    def set_input_device(self, device):
        """Set the audio input device."""
        self.audio.set_input_device(device)

    def set_delay(self, delay):
        """Set the audio delay, validating the range 0-10000 ms."""
        try:
            delay = int(delay)
            self._validate_delay(delay)
            self.config.set_delay(delay)
        except ValueError:
            logger.exception("Tried to set an invalid delay of %s ms", delay)
            messagebox.showerror("Invalid delay", "Delay must be within the range 0 to 10000")

    @staticmethod
    def _validate_delay(delay):
        """Raise ValueError if delay is out of range."""
        if delay < 0 or delay > _MAX_DELAY_MS:
            msg = f"Delay {delay} out of range 0-{_MAX_DELAY_MS}"
            raise ValueError(msg)


    def run(self):
        """Start the GUI event loop."""
        self.gui.run()

if __name__ == "__main__":
    main = Main()
    main.run()
