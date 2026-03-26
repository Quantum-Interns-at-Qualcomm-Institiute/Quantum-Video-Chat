"""
FrameSource / AudioSource — Abstract protocols for video and audio producers.

Decouples frame/chunk consumers (video threads, audio threads, AV namespaces)
from the specific source (camera, microphone, static noise, test patterns).

Implementing classes must provide ``capture()`` and ``release()``.
"""
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class FrameSource(ABC):
    """Abstract base class for video frame sources."""

    @abstractmethod
    def capture(self) -> Optional[np.ndarray]:
        """Return the next BGR frame, or None if unavailable."""

    @abstractmethod
    def release(self) -> None:
        """Release any held resources (camera handles, etc.)."""


class CameraSource(FrameSource):
    """Captures frames from a hardware camera via OpenCV."""

    def __init__(self, device: int = 0, width: int = 640, height: int = 480):
        from cv2 import VideoCapture, resize
        self._VideoCapture = VideoCapture
        self._resize = resize
        self.cap = VideoCapture(device)
        self.width = width
        self.height = height

    def capture(self) -> Optional[np.ndarray]:
        ret, frame = self.cap.read()
        if not ret:
            return None
        return self._resize(frame, dsize=(self.width, self.height))

    def release(self) -> None:
        self.cap.release()


class StaticNoiseSource(FrameSource):
    """Generates TV-static frames (random grey noise)."""

    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height

    def capture(self) -> Optional[np.ndarray]:
        return np.random.randint(
            30, 200, (self.height, self.width, 3), dtype=np.uint8)

    def release(self) -> None:
        pass  # no resources to release


class MockFrameSource(FrameSource):
    """Produces a fixed sequence of 10 deterministic, verifiable test frames.

    Frame N (0–9) has every pixel set to ``(N * 25, N * 25, N * 25)`` so each
    frame is visually distinct and trivially identifiable.  After all 10 frames
    have been emitted, ``capture()`` returns ``None``.

    Use ``frame_id(frame)`` to extract the sequence number from any frame
    produced by this source.

    Two independent ``MockFrameSource`` instances (e.g. one per test client)
    will emit the *same* deterministic sequence, making them ideal for
    end-to-end frame delivery assertions.
    """
    NUM_FRAMES = 10
    PIXEL_STEP = 25  # brightness increment per frame

    def __init__(self, width: int = 640, height: int = 480, looping: bool = False):
        self.width = width
        self.height = height
        self.looping = looping
        self._index = 0

    def capture(self) -> Optional[np.ndarray]:
        if self._index >= self.NUM_FRAMES:
            if self.looping:
                self._index = 0
            else:
                return None
        value = self._index * self.PIXEL_STEP
        frame = np.full(
            (self.height, self.width, 3), value, dtype=np.uint8,
        )
        self._index += 1
        return frame

    def release(self) -> None:
        pass  # no resources to release

    def reset(self) -> None:
        """Reset the source to re-emit all 10 frames."""
        self._index = 0

    @property
    def frames_emitted(self) -> int:
        """How many frames have been emitted so far."""
        return self._index

    @staticmethod
    def frame_id(frame: np.ndarray) -> int:
        """Extract the sequence number (0–9) from a MockFrameSource frame.

        Returns -1 if the frame does not match the expected pattern.
        """
        value = int(frame[0, 0, 0])
        if value % MockFrameSource.PIXEL_STEP != 0:
            return -1
        seq = value // MockFrameSource.PIXEL_STEP
        if seq < 0 or seq >= MockFrameSource.NUM_FRAMES:
            return -1
        # Verify the frame is uniform
        if not np.all(frame == value):
            return -1
        return seq


# ═══════════════════════════════════════════════════════════════════════════════
# Audio Sources
# ═══════════════════════════════════════════════════════════════════════════════


class AudioSource(ABC):
    """Abstract base class for audio chunk sources.

    ``capture()`` returns a 1-D ``float32`` numpy array of PCM samples
    (mono, range [-1.0, 1.0]), or ``None`` when no data is available.
    """

    @abstractmethod
    def capture(self) -> Optional[np.ndarray]:
        """Return the next audio chunk, or None if unavailable."""

    @abstractmethod
    def release(self) -> None:
        """Release any held resources (streams, handles, etc.)."""


class MicrophoneSource(AudioSource):
    """Captures audio from a hardware microphone via PyAudio."""

    def __init__(self, device_index: int = 0,
                 sample_rate: int = 8000,
                 frames_per_buffer: int = 1366):
        import pyaudio
        self._pa = pyaudio.PyAudio()
        self.sample_rate = sample_rate
        self.frames_per_buffer = frames_per_buffer
        self._stream = self._pa.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=frames_per_buffer,
        )

    def capture(self) -> Optional[np.ndarray]:
        try:
            data = self._stream.read(self.frames_per_buffer,
                                     exception_on_overflow=False)
            return np.frombuffer(data, dtype=np.float32)
        except Exception:
            return None

    def release(self) -> None:
        try:
            self._stream.stop_stream()
            self._stream.close()
        except Exception:
            pass
        try:
            self._pa.terminate()
        except Exception:
            pass


class SilenceSource(AudioSource):
    """Produces silent audio chunks (all zeros). Used when muted."""

    def __init__(self, frames_per_buffer: int = 1366):
        self.frames_per_buffer = frames_per_buffer

    def capture(self) -> Optional[np.ndarray]:
        return np.zeros(self.frames_per_buffer, dtype=np.float32)

    def release(self) -> None:
        pass


class MockAudioSource(AudioSource):
    """Produces 10 deterministic pure-tone audio chunks for testing.

    Chunk N (0–9) is a sine wave at frequency ``(N + 1) * BASE_FREQ`` Hz.
    After all 10 chunks have been emitted, ``capture()`` returns ``None``
    (unless ``looping=True``).

    Use ``chunk_id(chunk, sample_rate, frames_per_buffer)`` to extract the
    sequence number from any chunk produced by this source.
    """
    NUM_CHUNKS = 10
    BASE_FREQ = 200  # Hz — chunk N uses (N+1) * 200 Hz (max 2000 < Nyquist)

    def __init__(self, sample_rate: int = 8000,
                 frames_per_buffer: int = 1366,
                 looping: bool = False):
        self.sample_rate = sample_rate
        self.frames_per_buffer = frames_per_buffer
        self.looping = looping
        self._index = 0

    def capture(self) -> Optional[np.ndarray]:
        if self._index >= self.NUM_CHUNKS:
            if self.looping:
                self._index = 0
            else:
                return None
        freq = (self._index + 1) * self.BASE_FREQ
        t = np.arange(self.frames_per_buffer, dtype=np.float32) / self.sample_rate
        chunk = np.sin(2.0 * np.pi * freq * t).astype(np.float32)
        self._index += 1
        return chunk

    def release(self) -> None:
        pass

    def reset(self) -> None:
        """Reset the source to re-emit all 10 chunks."""
        self._index = 0

    @property
    def chunks_emitted(self) -> int:
        """How many chunks have been emitted so far."""
        return self._index

    @staticmethod
    def chunk_id(chunk: np.ndarray, sample_rate: int = 8000,
                 frames_per_buffer: int = 1366) -> int:
        """Extract the sequence number (0–9) from a MockAudioSource chunk.

        Uses FFT to find the dominant frequency and maps it back to the
        chunk index.  Returns -1 if the chunk doesn't match.
        """
        if len(chunk) < 2:
            return -1
        fft_mag = np.abs(np.fft.rfft(chunk))
        freqs = np.fft.rfftfreq(len(chunk), d=1.0 / sample_rate)
        dominant_freq = freqs[np.argmax(fft_mag)]
        # Map back: freq = (N+1) * BASE_FREQ → N = freq/BASE_FREQ - 1
        n_float = dominant_freq / MockAudioSource.BASE_FREQ - 1
        n = round(n_float)
        if n < 0 or n >= MockAudioSource.NUM_CHUNKS:
            return -1
        # Allow small tolerance for FFT bin rounding
        if abs(n_float - n) > 0.3:
            return -1
        return n
