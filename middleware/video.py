"""
VideoThread — Captures frames from the local camera and emits them.

Single responsibility: camera capture loop + frame emission.
Uses composition (owns a Thread) rather than inheriting from Thread.
Uses FrameSource protocol for camera/static frame abstraction.

Note: The ``shared`` package lives at the project root, which is not on
``sys.path`` when the middleware runs standalone from ``middleware/``.
We add the project root to ``sys.path`` so that ``shared.frame_source`` is
importable at runtime.
"""
import os
import sys
import threading
import gevent

# Ensure the project root is on sys.path so ``shared.*`` imports work.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shared.frame_source import CameraSource, StaticNoiseSource, MockFrameSource

# Special device indices for test sources (selected via the camera picker).
MOCK_DEVICE_A = -1
MOCK_DEVICE_B = -2


class VideoThread:
    """Captures frames from the local camera and emits them to all browsers."""

    def __init__(self, state, width: int, height: int, device: int = 0):
        self._thread = None
        self._stop_event = threading.Event()
        # Use MockFrameSource for special negative device indices,
        # real CameraSource for physical cameras.
        if device == MOCK_DEVICE_A or device == MOCK_DEVICE_B:
            self._camera_source = MockFrameSource(width=width, height=height, looping=True)
            print(f'(middleware): Using MockFrameSource (device={device})')
        else:
            self._camera_source = CameraSource(device=device, width=width, height=height)
        self._static_source = StaticNoiseSource(width=width, height=height)
        self.width  = width
        self.height = height
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
        interval = 0.1
        sio = self._state.sio
        server_client = self._state.server_client

        while not self._stop_event.is_set():
            source = (self._camera_source if self._state.camera_enabled
                      else self._static_source)
            frame = source.capture()

            if frame is not None:
                frame_list = frame.tolist()
                # Send to local browser (self-view)
                sio.emit('frame', {
                    'frame':  frame_list,
                    'width':  self.width,
                    'height': self.height,
                    'self':   True,
                })
                # Send to QKD server for relay to peer
                if server_client.connected:
                    try:
                        server_client.emit('frame', {
                            'frame':  frame_list,
                            'width':  self.width,
                            'height': self.height,
                        })
                    except Exception:
                        pass  # server disconnected mid-send
            gevent.sleep(interval)

        self._camera_source.release()
        print('(middleware): Video thread stopped.')

    def stop(self):
        self._stop_event.set()
