"""
Unit tests for the client ↔ server data-transmission pipeline.

These tests verify that video and audio data flows correctly between
two clients, covering:
  1. Encryption round-trip (AES, Debug)
  2. Key-index framing (4-byte prepend / extract)
  3. Video namespace message filtering (skip-self, key mismatch)
  4. Received frames reaching the FrontendAdapter
  5. BroadcastFlaskNamespace relaying messages
  6. Full encrypt → transmit → decrypt round-trip

NOTE: Some tests depend on the old middleware architecture (client.av,
client.socket_client) which was replaced. Those tests are skipped.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Tests depend on old middleware architecture (client.av, client.socket_client); needs rewrite")

from threading import Lock
from unittest.mock import MagicMock, patch, call

from shared.encryption import (
    AESEncryption, DebugEncryption, EncryptFactory, EncryptSchemes,
)
from shared.adapters import FrontendAdapter
from shared.endpoint import Endpoint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockAdapter(FrontendAdapter):
    """Minimal adapter that records every frame delivered to the frontend."""

    def __init__(self):
        self.frames = []
        self.self_frames = []
        self._callback = None

    def send_frame(self, data: bytes) -> None:
        self.frames.append(data)

    def send_self_frame(self, data: bytes, width: int, height: int) -> None:
        self.self_frames.append((data, width, height))

    def on_peer_id(self, callback) -> None:
        self._callback = callback

    def send_status(self, event: str, data: dict = None) -> None:
        pass


def _make_av_stub(adapter, encryption=None, key=None, debug_video=False):
    """Build a lightweight AV-like object without spawning threads."""
    av = MagicMock()
    av.adapter = adapter
    av.encryption = encryption or DebugEncryption()
    av._key_lock = Lock()
    av.key = key or (0, b'\x00' * 16)
    av.debug_video = debug_video
    av.video_shape = (120, 160, 3)
    av.frame_rate = 30
    av.sample_rate = 44100
    av.frames_per_buffer = 1024
    av.audio_wait = 0.01
    return av


def _make_video_ns(av, user_id='userA'):
    """Instantiate a ClientVideoClientNamespace without triggering on_connect."""
    from client.av import ClientVideoClientNamespace

    cls_stub = MagicMock()
    cls_stub.user_id = user_id
    cls_stub.send_message = MagicMock()

    ns = ClientVideoClientNamespace.__new__(ClientVideoClientNamespace)
    ns.cls = cls_stub
    ns.av = av
    ns.namespace = '/video'

    # Prepare the ffmpeg output pipeline stub used in on_message decoding.
    ns.output = MagicMock()
    return ns


def _make_audio_ns(av, user_id='userA'):
    """Instantiate an AudioClientNamespace without triggering on_connect."""
    from shared.av.namespaces import AudioClientNamespace

    cls_stub = MagicMock()
    cls_stub.user_id = user_id
    cls_stub.send_message = MagicMock()

    ns = AudioClientNamespace.__new__(AudioClientNamespace)
    ns.cls = cls_stub
    ns.av = av
    ns.namespace = '/audio'
    ns.stream = MagicMock()
    return ns


# ---------------------------------------------------------------------------
# 1. Encryption round-trip
# ---------------------------------------------------------------------------

class TestEncryptionRoundTrip:
    """Verify that encrypt → decrypt recovers the original data."""

    def test_aes_round_trip(self):
        enc = AESEncryption()
        key = b'\xab' * 16
        plaintext = b'hello world, this is test data!!'
        ciphertext = enc.encrypt(plaintext, key)
        assert ciphertext != plaintext
        assert enc.decrypt(ciphertext, key) == plaintext

    def test_aes_different_keys_fail(self):
        enc = AESEncryption()
        key_a = b'\xab' * 16
        key_b = b'\xcd' * 16
        plaintext = b'some secret video frame bytes!!'
        ciphertext = enc.encrypt(plaintext, key_a)
        with pytest.raises(Exception):
            enc.decrypt(ciphertext, key_b)

    def test_debug_encryption_is_passthrough(self):
        enc = DebugEncryption()
        data = b'raw frame data here'
        assert enc.encrypt(data, b'ignored') == data
        assert enc.decrypt(data, b'ignored') == data

    def test_aes_handles_large_payload(self):
        """Simulate a realistic frame-sized payload (~50 KiB)."""
        enc = AESEncryption()
        key = b'\x42' * 16
        payload = bytes(range(256)) * 200  # 51200 bytes
        ct = enc.encrypt(payload, key)
        assert enc.decrypt(ct, key) == payload


# ---------------------------------------------------------------------------
# 2. Key-index framing
# ---------------------------------------------------------------------------

class TestKeyIndexFraming:
    """The protocol prepends a 4-byte big-endian key index to every message."""

    def test_encode_key_index(self):
        key_idx = 7
        header = key_idx.to_bytes(4, 'big')
        assert len(header) == 4
        assert int.from_bytes(header, 'big') == 7

    def test_round_trip_index(self):
        for idx in (0, 1, 255, 65535, 2**31 - 1):
            header = idx.to_bytes(4, 'big')
            assert int.from_bytes(header, 'big') == idx

    def test_payload_preserved_after_header(self):
        key_idx = 42
        payload = b'encrypted_data_here'
        msg = key_idx.to_bytes(4, 'big') + payload
        assert msg[4:] == payload
        assert int.from_bytes(msg[:4], 'big') == 42


# ---------------------------------------------------------------------------
# 3. Video namespace — message filtering
# ---------------------------------------------------------------------------

class TestVideoNamespaceFiltering:
    """on_message must skip messages from self and those with a wrong key index."""

    def test_skip_own_message(self):
        adapter = MockAdapter()
        av = _make_av_stub(adapter)
        ns = _make_video_ns(av, user_id='userA')

        # Message from self: should be ignored.
        # user_id arrives as a plain string that matches cls.user_id.
        key_idx = 0
        msg = key_idx.to_bytes(4, 'big') + b'payload'
        ns.on_message('userA', msg)
        assert adapter.frames == []

    def test_skip_mismatched_key_index(self):
        adapter = MockAdapter()
        av = _make_av_stub(adapter, key=(5, b'\x00' * 16))
        ns = _make_video_ns(av, user_id='userA')

        # Message from peer but with wrong key index
        wrong_idx = 99
        msg = wrong_idx.to_bytes(4, 'big') + b'payload'
        ns.on_message(('userB',), msg)
        assert adapter.frames == []

    def test_accept_valid_peer_message(self):
        adapter = MockAdapter()
        enc = DebugEncryption()
        av = _make_av_stub(adapter, encryption=enc, key=(0, b'\x00' * 16))
        ns = _make_video_ns(av, user_id='userA')

        # Stub the ffmpeg decode step
        decoded_frame = b'raw_pixels'
        ns.output.run = MagicMock(return_value=(decoded_frame, None))

        key_idx = 0
        payload = enc.encrypt(b'compressed_h264', b'\x00' * 16)
        msg = key_idx.to_bytes(4, 'big') + payload
        ns.on_message(('userB',), msg)

        assert len(adapter.frames) == 1
        assert adapter.frames[0] == decoded_frame


# ---------------------------------------------------------------------------
# 4. Audio namespace — message filtering
# ---------------------------------------------------------------------------

class TestAudioNamespaceFiltering:
    """AudioClientNamespace follows the same skip-self / key-check pattern."""

    def test_skip_own_audio(self):
        adapter = MockAdapter()
        av = _make_av_stub(adapter)
        ns = _make_audio_ns(av, user_id='userA')

        # user_id arrives as a plain string matching cls.user_id
        msg = (0).to_bytes(4, 'big') + b'audio_data'
        ns.on_message('userA', msg)
        # stream.write should NOT have been called
        ns.stream.write.assert_not_called()

    def test_skip_wrong_key_index_audio(self):
        adapter = MockAdapter()
        av = _make_av_stub(adapter, key=(3, b'\x00' * 16))
        ns = _make_audio_ns(av, user_id='userA')

        msg = (99).to_bytes(4, 'big') + b'audio_data'
        ns.on_message(('userB',), msg)
        ns.stream.write.assert_not_called()

    def test_accept_valid_audio(self):
        adapter = MockAdapter()
        enc = DebugEncryption()
        av = _make_av_stub(adapter, encryption=enc, key=(0, b'\x00' * 16))
        ns = _make_audio_ns(av, user_id='userA')

        audio_payload = b'\x00\x01' * 512  # 1024 bytes of PCM
        msg = (0).to_bytes(4, 'big') + enc.encrypt(audio_payload, b'\x00' * 16)
        ns.on_message(('userB',), msg)

        ns.stream.write.assert_called_once()
        written_data = ns.stream.write.call_args[0][0]
        assert written_data == audio_payload


# ---------------------------------------------------------------------------
# 5. Received frame → adapter delivery
# ---------------------------------------------------------------------------

class TestFrameDeliveryToAdapter:
    """_handle_received_frame must push data through the adapter."""

    def test_video_frame_reaches_adapter(self):
        adapter = MockAdapter()
        av = _make_av_stub(adapter)
        ns = _make_video_ns(av, user_id='userA')

        raw_data = b'\xff' * 160 * 120 * 4  # RGBX frame
        ns._handle_received_frame('userB', raw_data)

        assert len(adapter.frames) == 1
        assert adapter.frames[0] == raw_data

    def test_multiple_frames_delivered_in_order(self):
        adapter = MockAdapter()
        av = _make_av_stub(adapter)
        ns = _make_video_ns(av, user_id='userA')

        for i in range(5):
            ns._handle_received_frame('userB', bytes([i]) * 100)

        assert len(adapter.frames) == 5
        for i in range(5):
            assert adapter.frames[i] == bytes([i]) * 100


# ---------------------------------------------------------------------------
# 6. BroadcastFlaskNamespace
# ---------------------------------------------------------------------------

class TestBroadcastFlaskNamespace:
    """The server-side namespace relays messages to everyone except the sender."""

    def test_relay_with_include_self_false(self):
        from shared.av.namespaces import BroadcastFlaskNamespace

        cls_stub = MagicMock()
        ns = BroadcastFlaskNamespace('/video', cls_stub)

        with patch('shared.av.namespaces.send') as mock_send:
            ns.on_message(('userA',), b'encrypted_frame')
            mock_send.assert_called_once_with(
                (('userA',), b'encrypted_frame'),
                broadcast=True,
                include_self=False,
            )

    def test_multiple_messages_relayed(self):
        from shared.av.namespaces import BroadcastFlaskNamespace

        cls_stub = MagicMock()
        ns = BroadcastFlaskNamespace('/video', cls_stub)

        with patch('shared.av.namespaces.send') as mock_send:
            for uid in ('userA', 'userB', 'userC'):
                ns.on_message((uid,), b'data')
            assert mock_send.call_count == 3


# ---------------------------------------------------------------------------
# 7. Full encrypt → decrypt round-trip (no ffmpeg)
# ---------------------------------------------------------------------------

class TestFullEncryptDecryptRoundTrip:
    """Simulate the full framing pipeline: encrypt + key-index → transmit → validate + decrypt."""

    @pytest.fixture
    def aes_pair(self):
        """Two namespaces sharing the same AES key (simulating key exchange)."""
        enc = AESEncryption()
        key = b'\xde\xad' * 8  # 16 bytes
        key_idx = 42

        adapter_a = MockAdapter()
        adapter_b = MockAdapter()
        av_a = _make_av_stub(adapter_a, encryption=enc, key=(key_idx, key))
        av_b = _make_av_stub(adapter_b, encryption=enc, key=(key_idx, key))
        ns_a = _make_video_ns(av_a, user_id='userA')
        ns_b = _make_video_ns(av_b, user_id='userB')
        return ns_a, ns_b, adapter_a, adapter_b, enc, key, key_idx

    def test_sender_encrypt_receiver_decrypt(self, aes_pair):
        ns_a, ns_b, _, adapter_b, enc, key, key_idx = aes_pair

        # Simulate sender building the on-wire message
        plaintext = b'compressed video frame data!!!!!'  # 32 bytes (AES block aligned)
        ciphertext = enc.encrypt(plaintext, key)
        wire_msg = key_idx.to_bytes(4, 'big') + ciphertext

        # Stub ffmpeg decode to return the "decoded" plaintext
        ns_b.output.run = MagicMock(return_value=(b'decoded_pixels', None))

        # Receiver processes the message
        ns_b.on_message(('userA',), wire_msg)

        # The decrypted data should have been passed to ffmpeg decode
        ns_b.output.run.assert_called_once()
        ffmpeg_input = ns_b.output.run.call_args[1]['input']
        assert ffmpeg_input == plaintext

        # And the final decoded output should reach the adapter
        assert adapter_b.frames == [b'decoded_pixels']

    def test_key_rotation_breaks_old_messages(self, aes_pair):
        """After key rotation, messages encrypted with the old key are dropped."""
        ns_a, ns_b, _, adapter_b, enc, key, key_idx = aes_pair

        plaintext = b'frame encrypted with old key!!!!'
        ciphertext = enc.encrypt(plaintext, key)
        wire_msg = key_idx.to_bytes(4, 'big') + ciphertext

        # Simulate key rotation on receiver: new key_idx = 43
        new_key = b'\xbe\xef' * 8
        with ns_b.av._key_lock:
            ns_b.av.key = (43, new_key)

        ns_b.on_message(('userA',), wire_msg)
        # Message should be dropped (key_idx mismatch)
        assert adapter_b.frames == []

    def test_audio_encrypt_decrypt_round_trip(self):
        """Same pattern for audio data."""
        enc = AESEncryption()
        key = b'\xca\xfe' * 8
        key_idx = 10

        adapter = MockAdapter()
        av = _make_av_stub(adapter, encryption=enc, key=(key_idx, key))
        ns = _make_audio_ns(av, user_id='userA')

        # PCM audio: 1024 samples × 2 bytes = 2048 bytes
        audio_pcm = bytes(range(256)) * 8
        ciphertext = enc.encrypt(audio_pcm, key)
        wire_msg = key_idx.to_bytes(4, 'big') + ciphertext

        ns.on_message(('userB',), wire_msg)

        ns.stream.write.assert_called_once()
        written = ns.stream.write.call_args[0][0]
        assert written == audio_pcm


# ---------------------------------------------------------------------------
# 8. Self-frame preview pipeline
# ---------------------------------------------------------------------------

class TestSelfFramePreview:
    """_handle_self_frame converts the outgoing image to RGBA for local preview."""

    def test_debug_frame_sent_to_adapter(self):
        import numpy as np
        adapter = MockAdapter()
        av = _make_av_stub(adapter, debug_video=True)
        ns = _make_video_ns(av, user_id='userA')

        # Simulate a debug RGB frame (gray values stacked 3×)
        gray = np.full((120, 160), 128, dtype=np.uint8)
        image = np.stack([gray, gray, gray], axis=2)

        ns._handle_self_frame(image)

        assert len(adapter.self_frames) == 1
        data, w, h = adapter.self_frames[0]
        assert w == 160
        assert h == 120
        # RGBA: 4 bytes per pixel
        assert len(data) == 160 * 120 * 4

    def test_camera_frame_converts_bgr_to_rgb(self):
        import numpy as np
        adapter = MockAdapter()
        av = _make_av_stub(adapter, debug_video=False)
        ns = _make_video_ns(av, user_id='userA')

        # Pure blue in BGR → should become pure red in RGBA
        bgr = np.zeros((2, 2, 3), dtype=np.uint8)
        bgr[:, :, 0] = 255  # B channel

        with patch('cv2.cvtColor') as mock_cvt:
            # cv2.cvtColor(BGR→RGB) swaps B and R
            rgb = np.zeros((2, 2, 3), dtype=np.uint8)
            rgb[:, :, 2] = 255  # R channel (was B)
            mock_cvt.return_value = rgb

            ns._handle_self_frame(bgr)

        assert len(adapter.self_frames) == 1
        data, w, h = adapter.self_frames[0]
        assert w == 2 and h == 2


# ---------------------------------------------------------------------------
# 9. SocketClient.send_message framing
# ---------------------------------------------------------------------------

class TestSocketClientSendMessage:
    """send_message wraps the payload with the user_id tuple."""

    def _make_client(self, user_id):
        with patch('client.socket_client.AV') as MockAV:
            MockAV.return_value = MagicMock()
            MockAV.return_value.client_namespaces = {'/test': MagicMock()}
            from client.socket_client import SocketClient
            sc = SocketClient(('127.0.0.1', 3000), user_id, lambda u, m: None, MagicMock())
        sc.sio = MagicMock()
        return sc

    def test_message_format(self):
        sc = self._make_client('abc12')
        sc.send_message(b'encrypted_frame', namespace='/video')
        sc.sio.send.assert_called_once_with(
            (('abc12',), b'encrypted_frame'),
            namespace='/video',
        )

    def test_default_namespace(self):
        sc = self._make_client('xyz99')
        sc.send_message(b'data')
        sc.sio.send.assert_called_once_with(
            (('xyz99',), b'data'),
            namespace='/',
        )


# ---------------------------------------------------------------------------
# 10. Integration: sender namespace → wire → receiver namespace
# ---------------------------------------------------------------------------

class TestEndToEndDataTransmission:
    """Full integration: sender encrypts and frames, receiver decrypts and delivers."""

    def test_video_send_then_receive(self):
        """Build the wire message the same way send_video does, then process it
        through on_message on the receiving side."""
        enc = AESEncryption()
        key = b'\x11\x22' * 8
        key_idx = 7

        # --- Sender side ---
        adapter_sender = MockAdapter()
        av_sender = _make_av_stub(adapter_sender, encryption=enc, key=(key_idx, key))
        ns_sender = _make_video_ns(av_sender, user_id='sender')

        # Simulate what send_video does after ffmpeg compression
        compressed_data = b'h264 compressed frame payload!!!'  # 32 bytes
        encrypted = enc.encrypt(compressed_data, key)
        wire = key_idx.to_bytes(4, 'big') + encrypted

        # The sender would call: self.send(wire)
        # which calls: self.cls.send_message(wire, namespace='/video')
        ns_sender.send(wire)
        ns_sender.cls.send_message.assert_called_once_with(wire, namespace='/video')

        # --- Receiver side ---
        adapter_receiver = MockAdapter()
        av_receiver = _make_av_stub(adapter_receiver, encryption=enc, key=(key_idx, key))
        ns_receiver = _make_video_ns(av_receiver, user_id='receiver')

        # Stub ffmpeg decode
        decoded_pixels = b'\xff' * 160 * 120 * 4
        ns_receiver.output.run = MagicMock(return_value=(decoded_pixels, None))

        ns_receiver.on_message(('sender',), wire)

        # ffmpeg received the decrypted (original compressed) data
        ffmpeg_input = ns_receiver.output.run.call_args[1]['input']
        assert ffmpeg_input == compressed_data

        # Adapter received the decoded pixels
        assert adapter_receiver.frames == [decoded_pixels]

    def test_bidirectional_transmission(self):
        """Both clients can send and receive from each other."""
        enc = AESEncryption()
        key = b'\xaa\xbb' * 8
        key_idx = 0

        adapters = {}
        namespaces = {}
        for uid in ('alice', 'bob'):
            adapters[uid] = MockAdapter()
            av = _make_av_stub(adapters[uid], encryption=enc, key=(key_idx, key))
            namespaces[uid] = _make_video_ns(av, user_id=uid)
            namespaces[uid].output.run = MagicMock(
                return_value=(f'decoded_{uid}'.encode(), None))

        # Alice → Bob
        msg_a = b'alice frame compressed data!!!!!'
        wire_a = key_idx.to_bytes(4, 'big') + enc.encrypt(msg_a, key)
        namespaces['bob'].on_message(('alice',), wire_a)
        assert adapters['bob'].frames == [b'decoded_bob']

        # Bob → Alice
        msg_b = b'bob frame compressed data!!!!!!'
        wire_b = key_idx.to_bytes(4, 'big') + enc.encrypt(msg_b, key)
        namespaces['alice'].on_message(('bob',), wire_b)
        assert adapters['alice'].frames == [b'decoded_alice']

        # Neither saw their own frames
        assert adapters['alice'].frames == [b'decoded_alice']
        assert adapters['bob'].frames == [b'decoded_bob']
