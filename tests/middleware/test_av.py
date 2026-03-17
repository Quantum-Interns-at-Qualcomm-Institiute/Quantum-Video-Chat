"""Tests for middleware/client/av.py — AV class and namespace generators."""
import pytest
from unittest.mock import MagicMock, patch


class TestAV:
    @patch('client.av.create_key_generator')
    @patch('client.av.create_encrypt_scheme')
    @patch('client.av.Thread')
    def test_constructor(self, MockThread, mock_create_encrypt, mock_create_keygen, mock_adapter):
        mock_encrypt = MagicMock()
        mock_create_encrypt.return_value = mock_encrypt

        mock_key_gen = MagicMock()
        mock_key_gen.get_key.return_value = b'\x00' * 16
        mock_create_keygen.return_value = mock_key_gen

        from client.av import AV
        av = AV(MagicMock(), mock_adapter)

        assert av.adapter is mock_adapter
        assert av.encryption is mock_encrypt
        MockThread.assert_called_once()
        MockThread.return_value.start.assert_called_once()

    @patch('client.av.create_key_generator')
    @patch('client.av.create_encrypt_scheme')
    @patch('client.av.Thread')
    def test_key_rotation_thread_is_daemon(self, MockThread, mock_create_encrypt, mock_create_keygen, mock_adapter):
        mock_key_gen = MagicMock()
        mock_key_gen.get_key.return_value = b'\x00' * 16
        mock_create_keygen.return_value = mock_key_gen

        from client.av import AV
        av = AV(MagicMock(), mock_adapter)

        # Verify Thread was called with daemon=True
        _, kwargs = MockThread.call_args
        assert kwargs.get('daemon') is True


class TestGenerateNamespaces:
    @patch('client.av.create_key_generator')
    @patch('client.av.create_encrypt_scheme')
    @patch('client.av.Thread')
    def test_client_namespaces_have_video_and_audio(self, MockThread, mock_create_encrypt, mock_create_keygen, mock_adapter):
        mock_key_gen = MagicMock()
        mock_key_gen.get_key.return_value = b'\x00' * 16
        mock_create_keygen.return_value = mock_key_gen

        from client.av import AV
        av = AV(MagicMock(), mock_adapter)

        assert '/video' in av.client_namespaces
        assert '/audio' in av.client_namespaces

    def test_generate_flask_namespace(self):
        from client.av import generate_flask_namespace
        cls = MagicMock()
        result = generate_flask_namespace(cls)
        assert '/video' in result
        assert '/audio' in result

    def test_test_mode_namespaces(self):
        import client.av as av_module
        original = av_module.testing
        try:
            av_module.testing = True
            cls = MagicMock()
            result = av_module.generate_flask_namespace(cls)
            assert '/test' in result
            assert '/video' not in result
        finally:
            av_module.testing = original


class TestClientVideoClientNamespace:
    """Targeted tests for the client-side video namespace implementation."""

    def test_pix_fmt_is_rgb0(self):
        """Encoding pipeline requires 'rgb0' (4 bytes/pixel); 'rgbx' is not a valid ffmpeg name."""
        from client.av import ClientVideoClientNamespace
        assert ClientVideoClientNamespace.pix_fmt == 'rgb0'

    def test_tobytes_produces_4_bytes_per_pixel(self):
        """_tobytes must return h*w*4 bytes for the rgb0 ffmpeg pixel format."""
        import numpy as np
        from client.av import ClientVideoClientNamespace
        ns = ClientVideoClientNamespace.__new__(ClientVideoClientNamespace)
        h, w = 4, 4
        gray = np.zeros((h, w), dtype=np.uint8)
        image = np.stack([gray, gray, gray], axis=2)  # (h, w, 3) BGR
        result = ns._tobytes(image)
        assert len(result) == h * w * 4  # 4 bytes per pixel (R, G, B, 0x00)

    def test_on_disconnect_does_not_raise(self):
        """on_disconnect was previously crashing with AttributeError (cls.client missing)."""
        from shared.av.namespaces import BroadcastFlaskNamespace
        ns = BroadcastFlaskNamespace.__new__(BroadcastFlaskNamespace)
        ns.cls = MagicMock()
        ns.namespace = '/video'
        ns.on_disconnect()  # must not raise


class TestAVSessionSettings:
    """Verify AV applies host session_settings and keeps debug_video local."""

    @patch('client.av.create_key_generator')
    @patch('client.av.create_encrypt_scheme')
    @patch('client.av.Thread')
    def test_uses_session_settings_overrides(self, MockThread, mock_create_encrypt, mock_create_keygen, mock_adapter):
        mock_key_gen = MagicMock()
        mock_key_gen.get_key.return_value = b'\x00' * 16
        mock_create_keygen.return_value = mock_key_gen

        from client.av import AV
        settings = {
            'video_width': 320,
            'video_height': 240,
            'frame_rate': 30,
            'sample_rate': 16000,
            'audio_wait': 0.25,
            'key_length': 256,
            'encrypt_scheme': 'AES',
            'key_generator': 'FILE',
        }
        av = AV(MagicMock(), mock_adapter, session_settings=settings)

        assert av.video_shape == (240, 320, 3)
        assert av.frame_rate == 30
        assert av.sample_rate == 16000
        assert av.audio_wait == 0.25
        assert av._key_length == 256

    @patch('client.av.create_key_generator')
    @patch('client.av.create_encrypt_scheme')
    @patch('client.av.Thread')
    def test_debug_video_stays_local(self, MockThread, mock_create_encrypt, mock_create_keygen, mock_adapter):
        """debug_video must always come from local config, never from session_settings."""
        mock_key_gen = MagicMock()
        mock_key_gen.get_key.return_value = b'\x00' * 16
        mock_create_keygen.return_value = mock_key_gen

        from client.av import AV
        from shared.config import DEBUG_VIDEO

        settings = {
            'video_width': 320,
            'video_height': 240,
            'frame_rate': 30,
            'sample_rate': 16000,
            'audio_wait': 0.25,
            'key_length': 128,
            'encrypt_scheme': 'AES',
            'key_generator': 'FILE',
        }
        av = AV(MagicMock(), mock_adapter, session_settings=settings)
        assert av.debug_video == DEBUG_VIDEO

    @patch('client.av.create_key_generator')
    @patch('client.av.create_encrypt_scheme')
    @patch('client.av.Thread')
    def test_defaults_when_no_session_settings(self, MockThread, mock_create_encrypt, mock_create_keygen, mock_adapter):
        """Without session_settings, AV uses local config values."""
        mock_key_gen = MagicMock()
        mock_key_gen.get_key.return_value = b'\x00' * 16
        mock_create_keygen.return_value = mock_key_gen

        from client.av import AV
        from shared.config import VIDEO_SHAPE, FRAME_RATE, SAMPLE_RATE, AUDIO_WAIT

        av = AV(MagicMock(), mock_adapter)
        assert av.video_shape == VIDEO_SHAPE
        assert av.frame_rate == FRAME_RATE
        assert av.sample_rate == SAMPLE_RATE
        assert av.audio_wait == AUDIO_WAIT

    @patch('client.av.create_key_generator')
    @patch('client.av.create_encrypt_scheme')
    @patch('client.av.Thread')
    def test_frames_per_buffer_derived_from_sample_rate(self, MockThread, mock_create_encrypt, mock_create_keygen, mock_adapter):
        """frames_per_buffer should be recalculated from the (possibly overridden) sample_rate."""
        mock_key_gen = MagicMock()
        mock_key_gen.get_key.return_value = b'\x00' * 16
        mock_create_keygen.return_value = mock_key_gen

        from client.av import AV
        settings = {
            'sample_rate': 12000,
            'encrypt_scheme': 'AES',
            'key_generator': 'FILE',
        }
        av = AV(MagicMock(), mock_adapter, session_settings=settings)
        assert av.frames_per_buffer == 12000 // 6
