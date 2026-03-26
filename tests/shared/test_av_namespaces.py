"""Tests for shared/av/namespaces.py — AV namespace classes."""
from unittest.mock import MagicMock, patch


class TestBroadcastFlaskNamespace:
    def test_on_message_calls_send_with_broadcast(self):
        from shared.av.namespaces import BroadcastFlaskNamespace
        ns = BroadcastFlaskNamespace('/video', MagicMock())
        with patch('shared.av.namespaces.send') as mock_send:
            ns.on_message(('user1',), b'frame_data')
            mock_send.assert_called_once_with(
                (('user1',), b'frame_data'),
                broadcast=True, include_self=False,
            )

    def test_on_message_preserves_user_id_tuple(self):
        from shared.av.namespaces import BroadcastFlaskNamespace
        ns = BroadcastFlaskNamespace('/audio', MagicMock())
        with patch('shared.av.namespaces.send') as mock_send:
            ns.on_message(('abc',), b'audio_chunk')
            args = mock_send.call_args[0][0]
            assert args[0] == ('abc',)
            assert args[1] == b'audio_chunk'


class TestTestFlaskNamespace:
    def test_on_message_broadcasts(self):
        from shared.av.namespaces import TestFlaskNamespace
        ns = TestFlaskNamespace('/test', MagicMock())
        with patch('shared.av.namespaces.send') as mock_send:
            ns.on_message(('user1',), 'hello')
            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args[1]
            assert call_kwargs['broadcast'] is True


class TestTestClientNamespace:
    def test_on_connect_calls_display_message(self):
        from shared.av.namespaces import TestClientNamespace
        mock_cls = MagicMock()
        mock_av = MagicMock()
        ns = TestClientNamespace('/test', mock_cls, mock_av)
        with patch('shared.av.namespaces.display_message') as mock_disp:
            ns.on_connect()
            mock_disp.assert_called_once()

    def test_on_message_calls_display_message(self):
        from shared.av.namespaces import TestClientNamespace
        mock_cls = MagicMock()
        mock_av = MagicMock()
        ns = TestClientNamespace('/test', mock_cls, mock_av)
        with patch('shared.av.namespaces.display_message') as mock_disp:
            ns.on_message(('user1',), 'hello world')
            mock_disp.assert_called_once()
            call_args = mock_disp.call_args[0]
            assert '/test: ' in call_args[1]  # message prefixed with namespace


class TestAVClientNamespace:
    def test_send_delegates_to_cls(self):
        from shared.av.namespaces import AVClientNamespace
        mock_cls = MagicMock()
        mock_av = MagicMock()
        ns = AVClientNamespace('/video', mock_cls, mock_av)
        ns.send(b'data')
        mock_cls.send_message.assert_called_once_with(b'data', namespace='/video')


class TestKeyClientNamespace:
    def test_on_connect_starts_key_thread(self):
        """on_connect should start a daemon thread for key distribution."""
        from shared.av.namespaces import KeyClientNamespace
        mock_cls = MagicMock()
        mock_av = MagicMock()
        ns = KeyClientNamespace('/key', mock_cls, mock_av)

        with patch('shared.av.namespaces.Thread') as MockThread:
            ns.on_connect()
            MockThread.assert_called_once()
            call_kwargs = MockThread.call_args[1]
            assert call_kwargs['daemon'] is True
            MockThread.return_value.start.assert_called_once()


class TestVideoClientNamespaceFiltering:
    """Test the on_message filtering logic (skip self, key mismatch)."""

    def _make_ns(self):
        from shared.av.namespaces import VideoClientNamespace

        class ConcreteVideoNS(VideoClientNamespace):
            pix_fmt = 'rgb24'
            def _tobytes(self, image):
                return image.tobytes()
            def _handle_received_frame(self, user_id, raw_data):
                self.received_frames.append((user_id, raw_data))
            def _handle_self_frame(self, image):
                pass

        mock_cls = MagicMock()
        mock_cls.user_id = 'me'
        mock_av = MagicMock()
        mock_av._key_lock = MagicMock()
        mock_av.key = (0, b'0' * 16)
        mock_av.encryption = MagicMock()
        mock_av.video_shape = (10, 10, 3)
        mock_av.display_shape = (10, 10, 3)
        mock_av.frame_rate = 15

        ns = ConcreteVideoNS('/video', mock_cls, mock_av)
        ns.received_frames = []
        # Set the output attribute that on_connect() would normally create
        ns.output = MagicMock()
        return ns

    def test_skip_own_message(self):
        ns = self._make_ns()
        # Key index 0 as 4-byte header + payload
        key_idx_bytes = (0).to_bytes(4, 'big')
        # SocketIO unpacks tuples, so user_id arrives as a plain string
        ns.on_message('me', key_idx_bytes + b'encrypted_frame')
        assert len(ns.received_frames) == 0  # own message skipped

    def test_skip_mismatched_key_index(self):
        ns = self._make_ns()
        # Current key index is 0, but message has key index 99
        key_idx_bytes = (99).to_bytes(4, 'big')
        ns.on_message('peer', key_idx_bytes + b'encrypted_frame')
        assert len(ns.received_frames) == 0  # mismatched key skipped

    def test_valid_peer_frame_processed(self):
        ns = self._make_ns()
        key_idx_bytes = (0).to_bytes(4, 'big')
        ns.on_message('peer', key_idx_bytes + b'encrypted_frame')
        # The decryption + output.run pipeline should have been called
        ns.av.encryption.decrypt.assert_called_once()
        ns.output.run.assert_called_once()


class TestAudioClientNamespaceFiltering:
    """Test the audio on_message filtering logic."""

    def _make_audio_ns(self):
        from shared.av.namespaces import AudioClientNamespace
        mock_cls = MagicMock()
        mock_cls.user_id = 'me'
        mock_av = MagicMock()
        mock_av._key_lock = MagicMock()
        mock_av.key = (0, b'0' * 16)
        mock_av.encryption = MagicMock()
        mock_av.sample_rate = 8000
        mock_av.frames_per_buffer = 1366
        mock_av.audio_wait = 0.125
        mock_av.mute_audio = False

        ns = AudioClientNamespace('/audio', mock_cls, mock_av)
        # Set the stream attribute that on_connect() would normally create
        ns.stream = MagicMock()
        return ns

    def test_skip_own_audio(self):
        ns = self._make_audio_ns()
        key_idx_bytes = (0).to_bytes(4, 'big')
        # SocketIO unpacks tuples, so user_id arrives as a plain string
        ns.on_message('me', key_idx_bytes + b'encrypted_audio')
        # Own message skipped — stream.write should NOT be called
        ns.stream.write.assert_not_called()

    def test_skip_wrong_key_index_audio(self):
        ns = self._make_audio_ns()
        key_idx_bytes = (99).to_bytes(4, 'big')
        ns.on_message('peer', key_idx_bytes + b'encrypted_audio')
        # Mismatched key index — stream.write should NOT be called
        ns.stream.write.assert_not_called()

    def test_valid_peer_audio_played(self):
        ns = self._make_audio_ns()
        key_idx_bytes = (0).to_bytes(4, 'big')
        ns.on_message('peer', key_idx_bytes + b'encrypted_audio')
        # Should decrypt and write to stream
        ns.av.encryption.decrypt.assert_called_once()
        ns.stream.write.assert_called_once()
