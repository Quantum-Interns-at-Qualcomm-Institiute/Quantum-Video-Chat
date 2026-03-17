"""
AudioThread — Captures audio from a microphone and emits chunks.

Single responsibility: audio capture loop + chunk emission.
Uses composition (owns a Thread) rather than inheriting from Thread.
Uses AudioSource protocol for microphone/silence/mock abstraction.
Mirrors VideoThread in video.py.
"""
import os
import sys
import threading
import gevent

# Ensure the project root is on sys.path so ``shared.*`` imports work.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shared.frame_source import MicrophoneSource, SilenceSource, MockAudioSource

# Special device indices for test sources (selected via the audio device picker).
MOCK_AUDIO_DEVICE_A = -1
MOCK_AUDIO_DEVICE_B = -2

# Default audio parameters
DEFAULT_SAMPLE_RATE = 8196
DEFAULT_FRAMES_PER_BUFFER = DEFAULT_SAMPLE_RATE // 6  # ~1366


class AudioThread:
    """Captures audio from a microphone and emits chunks to all browsers."""

    def __init__(self, state, sample_rate: int = DEFAULT_SAMPLE_RATE,
                 frames_per_buffer: int = DEFAULT_FRAMES_PER_BUFFER,
                 device: int = 0):
        self._thread = None
        self._stop_event = threading.Event()
        self.sample_rate = sample_rate
        self.frames_per_buffer = frames_per_buffer

        # Use MockAudioSource for special negative device indices,
        # real MicrophoneSource for physical devices.
        if device == MOCK_AUDIO_DEVICE_A or device == MOCK_AUDIO_DEVICE_B:
            self._mic_source = MockAudioSource(
                sample_rate=sample_rate,
                frames_per_buffer=frames_per_buffer,
                looping=True,
            )
            print(f'(middleware): Using MockAudioSource (device={device})')
        else:
            self._mic_source = MicrophoneSource(
                device_index=device,
                sample_rate=sample_rate,
                frames_per_buffer=frames_per_buffer,
            )
        self._silence_source = SilenceSource(frames_per_buffer=frames_per_buffer)
        self._state = state

    # ── Thread delegation ─────────────────────────────────────────────────

    def start(self):
        """Launch the capture loop on a background daemon thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def is_alive(self):
        """Return True if the background thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout=None):
        """Block until the background thread terminates."""
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
                chunk_list = chunk.tolist()
                # Send to local browser (self-monitor)
                sio.emit('audio-frame', {
                    'audio':       chunk_list,
                    'sample_rate': self.sample_rate,
                    'self':        True,
                })
                # Send to QKD server for relay to peer
                if server_client.connected:
                    try:
                        server_client.emit('audio-frame', {
                            'audio':       chunk_list,
                            'sample_rate': self.sample_rate,
                        })
                    except Exception:
                        pass  # server disconnected mid-send
            gevent.sleep(interval)

        self._mic_source.release()
        print('(middleware): Audio thread stopped.')

    def stop(self):
        self._stop_event.set()
