"""AudioThread — Captures audio from a microphone and emits chunks.

Single responsibility: audio capture loop + chunk emission.
Uses composition (owns a Thread) rather than inheriting from Thread.
Uses AudioSource protocol for microphone/silence/mock abstraction.
Mirrors VideoThread in video.py.
"""
import base64
import sys
import threading
from pathlib import Path

import gevent

# Ensure the project root is on sys.path so ``shared.*`` imports work.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shared.frame_source import MicrophoneSource, MockAudioSource, SilenceSource
from shared.logging import get_logger

logger = get_logger(__name__)

# Special device indices for test sources (selected via the audio device picker).
MOCK_AUDIO_DEVICE_A = -1
MOCK_AUDIO_DEVICE_B = -2

# Default audio parameters
DEFAULT_SAMPLE_RATE = 8000
DEFAULT_FRAMES_PER_BUFFER = DEFAULT_SAMPLE_RATE // 6  # ~1366


class AudioThread:
    """Captures audio from a microphone and emits chunks to all browsers."""

    def __init__(self, state, sample_rate: int = DEFAULT_SAMPLE_RATE,
                 frames_per_buffer: int = DEFAULT_FRAMES_PER_BUFFER,
                 device: int = 0):
        """Initialize the audio capture thread."""
        logger.debug("AudioThread.__init__  device=%s  rate=%s  buf=%s",
                     device, sample_rate, frames_per_buffer)
        self._thread = None
        self._stop_event = threading.Event()
        self.sample_rate = sample_rate
        self.frames_per_buffer = frames_per_buffer

        # Use MockAudioSource for special negative device indices,
        # real MicrophoneSource for physical devices.
        if device in (MOCK_AUDIO_DEVICE_A, MOCK_AUDIO_DEVICE_B):
            self._mic_source = MockAudioSource(
                sample_rate=sample_rate,
                frames_per_buffer=frames_per_buffer,
                looping=True,
            )
            logger.info("Using MockAudioSource (device=%s)", device)
        else:
            logger.info("Using MicrophoneSource (device=%s)", device)
            self._mic_source = MicrophoneSource(
                device_index=device,
                sample_rate=sample_rate,
                frames_per_buffer=frames_per_buffer,
            )
        self._silence_source = SilenceSource(frames_per_buffer=frames_per_buffer)
        self._state = state
        logger.debug("AudioThread initialized")

    # ── Thread delegation ─────────────────────────────────────────────────

    def start(self):
        """Launch the capture loop on a background daemon thread."""
        logger.info("AudioThread starting capture loop")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def is_alive(self):
        """Return True if the background thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout=None):
        """Block until the background thread terminates."""
        logger.debug("AudioThread.join(timeout=%s)", timeout)
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self):
        interval = 0.125  # ~8 chunks/sec
        sio = self._state.sio
        server_client = self._state.server_client

        while not self._stop_event.is_set():
            source = (self._silence_source if self._state.muted
                      else self._mic_source)
            chunk = source.capture()

            if chunk is not None:
                # Encode audio as base64 for efficient transport
                chunk_b64 = base64.b64encode(chunk.tobytes()).decode("ascii")
                # Send to local browser (self-monitor)
                sio.emit("audio-frame", {
                    "audio":       chunk_b64,
                    "sample_rate": self.sample_rate,
                    "self":        True,
                })
                # Send to QKD server for relay to peer
                if server_client.connected:
                    try:
                        server_client.emit("audio-frame", {
                            "audio":       chunk_b64,
                            "sample_rate": self.sample_rate,
                        })
                    except (ConnectionError, OSError):
                        logger.debug("Audio send failed (server disconnected mid-send)")
            gevent.sleep(interval)

        self._mic_source.release()
        logger.info("Audio thread stopped.")

    def stop(self):
        """Signal the capture loop to stop."""
        logger.info("AudioThread stopping")
        self._stop_event.set()
