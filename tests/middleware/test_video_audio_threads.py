"""Tests for middleware/video.py and middleware/audio.py — capture threads."""
import threading
import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch, PropertyMock
from tests.middleware._helpers import load_middleware_module

mw_video = load_middleware_module('video')
mw_audio = load_middleware_module('audio')

VideoThread = mw_video.VideoThread
AudioThread = mw_audio.AudioThread
MOCK_DEVICE_A = mw_video.MOCK_DEVICE_A
MOCK_DEVICE_B = mw_video.MOCK_DEVICE_B
MOCK_AUDIO_DEVICE_A = mw_audio.MOCK_AUDIO_DEVICE_A
MOCK_AUDIO_DEVICE_B = mw_audio.MOCK_AUDIO_DEVICE_B


@pytest.fixture
def mock_state():
    """State with mocked sio and server_client."""
    s = MagicMock()
    s.sio = MagicMock()
    s.server_client = MagicMock()
    s.server_client.connected = False
    s.camera_enabled = True
    s.muted = False
    return s


# ─── VideoThread ──────────────────────────────────────────────────────────────

class TestVideoThread:
    def test_mock_device_constants(self):
        assert MOCK_DEVICE_A == -1
        assert MOCK_DEVICE_B == -2

    def test_init_with_mock_device(self, mock_state):
        vt = VideoThread(mock_state, 640, 480, device=MOCK_DEVICE_A)
        assert vt.width == 640
        assert vt.height == 480
        # Should use MockFrameSource for negative device indices
        assert 'MockFrameSource' in type(vt._camera_source).__name__

    def test_init_with_real_device(self, mock_state):
        with patch.object(mw_video, 'CameraSource') as MockCam:
            vt = VideoThread(mock_state, 320, 240, device=0)
        assert vt.width == 320
        assert vt.height == 240
        MockCam.assert_called_once_with(device=0, width=320, height=240)

    def test_is_alive_false_before_start(self, mock_state):
        vt = VideoThread(mock_state, 640, 480, device=MOCK_DEVICE_A)
        assert vt.is_alive() is False

    def test_start_and_stop(self, mock_state):
        vt = VideoThread(mock_state, 640, 480, device=MOCK_DEVICE_A)
        vt.start()
        assert vt.is_alive() is True
        vt.stop()
        vt.join(timeout=2)
        assert vt.is_alive() is False

    def test_emits_self_view_frames(self, mock_state):
        """VideoThread should emit frames to the local browser with self=True."""
        vt = VideoThread(mock_state, 64, 48, device=MOCK_DEVICE_A)
        vt.start()
        # Let it run briefly
        time.sleep(0.3)
        vt.stop()
        vt.join(timeout=2)

        # Should have emitted at least one frame
        calls = mock_state.sio.emit.call_args_list
        frame_calls = [c for c in calls if c[0][0] == 'frame']
        assert len(frame_calls) > 0
        # First frame should be self-view
        first_frame = frame_calls[0][0][1]
        assert first_frame['self'] is True
        assert 'frame' in first_frame
        assert first_frame['width'] == 64
        assert first_frame['height'] == 48

    def test_emits_to_server_when_connected(self, mock_state):
        """When server_client is connected, frames are also sent to server."""
        mock_state.server_client.connected = True
        vt = VideoThread(mock_state, 64, 48, device=MOCK_DEVICE_A)
        vt.start()
        time.sleep(0.3)
        vt.stop()
        vt.join(timeout=2)

        mock_state.server_client.emit.assert_called()
        call_args = mock_state.server_client.emit.call_args_list[0]
        assert call_args[0][0] == 'frame'

    def test_uses_static_noise_when_camera_disabled(self, mock_state):
        """When camera is disabled, should use StaticNoiseSource."""
        mock_state.camera_enabled = False
        vt = VideoThread(mock_state, 64, 48, device=MOCK_DEVICE_A)
        # Replace the static source with a mock to verify it's used
        mock_static = MagicMock()
        mock_static.capture.return_value = np.zeros((48, 64, 3), dtype=np.uint8)
        vt._static_source = mock_static

        vt.start()
        time.sleep(0.3)
        vt.stop()
        vt.join(timeout=2)

        mock_static.capture.assert_called()

    def test_stop_releases_camera(self, mock_state):
        vt = VideoThread(mock_state, 64, 48, device=MOCK_DEVICE_A)
        mock_camera = MagicMock()
        vt._camera_source = mock_camera
        vt.start()
        time.sleep(0.15)
        vt.stop()
        vt.join(timeout=2)
        mock_camera.release.assert_called_once()


# ─── AudioThread ──────────────────────────────────────────────────────────────

class TestAudioThread:
    def test_mock_device_constants(self):
        assert MOCK_AUDIO_DEVICE_A == -1
        assert MOCK_AUDIO_DEVICE_B == -2

    def test_init_with_mock_device(self, mock_state):
        at = AudioThread(mock_state, device=MOCK_AUDIO_DEVICE_A)
        assert 'MockAudioSource' in type(at._mic_source).__name__

    def test_init_with_real_device(self, mock_state):
        with patch.object(mw_audio, 'MicrophoneSource') as MockMic:
            at = AudioThread(mock_state, device=0)
        MockMic.assert_called_once()

    def test_is_alive_false_before_start(self, mock_state):
        at = AudioThread(mock_state, device=MOCK_AUDIO_DEVICE_A)
        assert at.is_alive() is False

    def test_start_and_stop(self, mock_state):
        at = AudioThread(mock_state, device=MOCK_AUDIO_DEVICE_A)
        at.start()
        assert at.is_alive() is True
        at.stop()
        at.join(timeout=2)
        assert at.is_alive() is False

    def test_emits_audio_frames(self, mock_state):
        at = AudioThread(mock_state, device=MOCK_AUDIO_DEVICE_A)
        at.start()
        time.sleep(0.4)
        at.stop()
        at.join(timeout=2)

        calls = mock_state.sio.emit.call_args_list
        audio_calls = [c for c in calls if c[0][0] == 'audio-frame']
        assert len(audio_calls) > 0
        first = audio_calls[0][0][1]
        assert first['self'] is True
        assert 'audio' in first
        assert 'sample_rate' in first

    def test_emits_to_server_when_connected(self, mock_state):
        mock_state.server_client.connected = True
        at = AudioThread(mock_state, device=MOCK_AUDIO_DEVICE_A)
        at.start()
        time.sleep(0.4)
        at.stop()
        at.join(timeout=2)

        mock_state.server_client.emit.assert_called()
        call_args = mock_state.server_client.emit.call_args_list[0]
        assert call_args[0][0] == 'audio-frame'

    def test_uses_silence_when_muted(self, mock_state):
        mock_state.muted = True
        at = AudioThread(mock_state, device=MOCK_AUDIO_DEVICE_A)
        mock_silence = MagicMock()
        mock_silence.capture.return_value = np.zeros(1366, dtype=np.int16)
        at._silence_source = mock_silence

        at.start()
        time.sleep(0.4)
        at.stop()
        at.join(timeout=2)

        mock_silence.capture.assert_called()

    def test_stop_releases_mic(self, mock_state):
        at = AudioThread(mock_state, device=MOCK_AUDIO_DEVICE_A)
        mock_mic = MagicMock()
        at._mic_source = mock_mic
        at.start()
        time.sleep(0.2)
        at.stop()
        at.join(timeout=2)
        mock_mic.release.assert_called_once()
