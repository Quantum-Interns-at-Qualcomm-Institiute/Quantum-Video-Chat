"""
Full end-to-end integration test with mock A/V devices.

Simulates the complete lifecycle:
  1. Server starts
  2. Two clients register with the server
  3. Client A opens a room (starts session)
  4. Client B joins Client A's room
  5. Server starts WebSocket API, both clients connect
  6. Audio and video frames from both clients are relayed to the peer
  7. Frames arrive intact and in correct order
  8. Both clients disconnect
  9. Server state is clean

Uses MockFrameSource and MockAudioSource instead of real hardware.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from shared.endpoint import Endpoint
from shared.frame_source import MockFrameSource, MockAudioSource


# ---------------------------------------------------------------------------
# Helpers — minimal relay simulator
# ---------------------------------------------------------------------------

class MockMiddleware:
    """Simulates one middleware process with mock A/V sources."""

    def __init__(self, user_id, width=8, height=6,
                 sample_rate=8196, frames_per_buffer=1366):
        self.user_id = user_id
        self.video_src = MockFrameSource(width=width, height=height)
        self.audio_src = MockAudioSource(
            sample_rate=sample_rate,
            frames_per_buffer=frames_per_buffer,
        )
        self.received_video = []
        self.received_audio = []
        self.self_video = []
        self.self_audio = []
        self.width = width
        self.height = height
        self.sample_rate = sample_rate

    def capture_and_emit_video(self):
        """Capture one video frame and return it as a wire-format dict."""
        frame = self.video_src.capture()
        if frame is None:
            return None
        payload = {
            'frame': frame.tolist(),
            'width': self.width,
            'height': self.height,
        }
        # Record self-view
        self.self_video.append(payload)
        return payload

    def capture_and_emit_audio(self):
        """Capture one audio chunk and return it as a wire-format dict."""
        chunk = self.audio_src.capture()
        if chunk is None:
            return None
        payload = {
            'audio': chunk.tolist(),
            'sample_rate': self.sample_rate,
        }
        self.self_audio.append(payload)
        return payload

    def receive_video(self, data):
        """Receive a relayed video frame from the peer."""
        self.received_video.append(data)

    def receive_audio(self, data):
        """Receive a relayed audio chunk from the peer."""
        self.received_audio.append(data)


class MockSocketAPIRelay:
    """Simulates the server's SocketAPI frame relay."""

    def __init__(self, middlewares):
        self.middlewares = {m.user_id: m for m in middlewares}

    def relay_video(self, sender_id, data):
        """Forward video frame to all peers except sender."""
        for uid, mw in self.middlewares.items():
            if uid != sender_id:
                mw.receive_video({
                    'frame': data['frame'],
                    'width': data['width'],
                    'height': data['height'],
                    'sender': sender_id,
                })

    def relay_audio(self, sender_id, data):
        """Forward audio chunk to all peers except sender."""
        for uid, mw in self.middlewares.items():
            if uid != sender_id:
                mw.receive_audio({
                    'audio': data['audio'],
                    'sample_rate': data['sample_rate'],
                    'sender': sender_id,
                })


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_server():
    """Create a Server with SocketAPI mocked out."""
    MockSocketAPI = MagicMock()
    MockSocketAPI.DEFAULT_ENDPOINT = MagicMock()
    MockSocketAPI.DEFAULT_ENDPOINT.__iter__ = MagicMock(
        return_value=iter(('127.0.0.1', 3000)))

    with patch.dict('sys.modules', {'socket_api': MagicMock(SocketAPI=MockSocketAPI)}):
        import importlib
        import server as server_mod
        importlib.reload(server_mod)
        Server = server_mod.Server

        s = Server(Endpoint('127.0.0.1', 5050))
        s._SocketAPI = MockSocketAPI
        yield s


@pytest.fixture
def two_clients_and_relay():
    """Two MockMiddleware instances + a relay."""
    mw_a = MockMiddleware('clientA', width=8, height=6)
    mw_b = MockMiddleware('clientB', width=8, height=6)
    relay = MockSocketAPIRelay([mw_a, mw_b])
    return mw_a, mw_b, relay


# ---------------------------------------------------------------------------
# 1. Server lifecycle — register, connect, disconnect
# ---------------------------------------------------------------------------

class TestServerLifecycle:
    """Server registers users, connects them, and cleans up on disconnect."""

    def test_register_two_users(self, mock_server):
        uid_a = mock_server.add_user(('127.0.0.1', 5001))
        uid_b = mock_server.add_user(('127.0.0.1', 5002))
        assert uid_a != uid_b
        assert mock_server.user_manager.storage.has_user(uid_a)
        assert mock_server.user_manager.storage.has_user(uid_b)

    def test_connect_and_disconnect(self, mock_server):
        uid_a = mock_server.add_user(('127.0.0.1', 5001))
        uid_b = mock_server.add_user(('127.0.0.1', 5002))

        from utils.user import UserState
        mock_server.set_user_state(uid_a, UserState.CONNECTED, peer=uid_b)
        mock_server.set_user_state(uid_b, UserState.CONNECTED, peer=uid_a)

        # Verify connected state
        assert mock_server.get_user(uid_a).state == UserState.CONNECTED
        assert mock_server.get_user(uid_b).state == UserState.CONNECTED

        # Disconnect
        mock_server.contact_client = MagicMock()
        mock_server.disconnect_peer(uid_a)

        assert mock_server.get_user(uid_a).state == UserState.IDLE
        assert mock_server.get_user(uid_b).state == UserState.IDLE

    def test_dashboard_call_count(self, mock_server):
        """call_count reflects only CONNECTED users."""
        uid_a = mock_server.add_user(('127.0.0.1', 5001))
        uid_b = mock_server.add_user(('127.0.0.1', 5002))
        uid_c = mock_server.add_user(('127.0.0.1', 5003))

        from utils.user import UserState

        # No one connected → 0 calls
        all_users = mock_server.user_manager.get_all_users()
        connected = sum(1 for u in all_users.values()
                        if u.get('state') == 'CONNECTED')
        assert connected // 2 == 0

        # A and B connected → 1 call
        mock_server.set_user_state(uid_a, UserState.CONNECTED, peer=uid_b)
        mock_server.set_user_state(uid_b, UserState.CONNECTED, peer=uid_a)

        all_users = mock_server.user_manager.get_all_users()
        connected = sum(1 for u in all_users.values()
                        if u.get('state') == 'CONNECTED')
        assert connected // 2 == 1


# ---------------------------------------------------------------------------
# 2. Video frame delivery — 10 frames from each client
# ---------------------------------------------------------------------------

class TestVideoFrameDelivery:
    """Both clients send 10 mock video frames; each receives the other's 10."""

    def test_all_10_video_frames_delivered_in_order(self, two_clients_and_relay):
        mw_a, mw_b, relay = two_clients_and_relay

        # Both clients send 10 frames
        for _ in range(10):
            v_a = mw_a.capture_and_emit_video()
            relay.relay_video('clientA', v_a)
            v_b = mw_b.capture_and_emit_video()
            relay.relay_video('clientB', v_b)

        # Client B received 10 frames from Client A
        assert len(mw_b.received_video) == 10
        for i, data in enumerate(mw_b.received_video):
            frame = np.array(data['frame'], dtype=np.uint8)
            assert MockFrameSource.frame_id(frame) == i
            assert data['sender'] == 'clientA'

        # Client A received 10 frames from Client B
        assert len(mw_a.received_video) == 10
        for i, data in enumerate(mw_a.received_video):
            frame = np.array(data['frame'], dtype=np.uint8)
            assert MockFrameSource.frame_id(frame) == i
            assert data['sender'] == 'clientB'

    def test_self_view_records_all_10(self, two_clients_and_relay):
        mw_a, _, relay = two_clients_and_relay
        for _ in range(10):
            v = mw_a.capture_and_emit_video()
            relay.relay_video('clientA', v)
        assert len(mw_a.self_video) == 10

    def test_no_self_echo_in_received(self, two_clients_and_relay):
        mw_a, mw_b, relay = two_clients_and_relay
        for _ in range(10):
            v_a = mw_a.capture_and_emit_video()
            relay.relay_video('clientA', v_a)
        # A should NOT have received any of its own frames
        assert len(mw_a.received_video) == 0


# ---------------------------------------------------------------------------
# 3. Audio chunk delivery — 10 chunks from each client
# ---------------------------------------------------------------------------

class TestAudioChunkDelivery:
    """Both clients send 10 mock audio chunks; each receives the other's 10."""

    def test_all_10_audio_chunks_delivered_in_order(self, two_clients_and_relay):
        mw_a, mw_b, relay = two_clients_and_relay

        for _ in range(10):
            a_a = mw_a.capture_and_emit_audio()
            relay.relay_audio('clientA', a_a)
            a_b = mw_b.capture_and_emit_audio()
            relay.relay_audio('clientB', a_b)

        # Client B received 10 chunks from Client A
        assert len(mw_b.received_audio) == 10
        for i, data in enumerate(mw_b.received_audio):
            chunk = np.array(data['audio'], dtype=np.float32)
            assert MockAudioSource.chunk_id(chunk) == i
            assert data['sender'] == 'clientA'

        # Client A received 10 chunks from Client B
        assert len(mw_a.received_audio) == 10
        for i, data in enumerate(mw_a.received_audio):
            chunk = np.array(data['audio'], dtype=np.float32)
            assert MockAudioSource.chunk_id(chunk) == i
            assert data['sender'] == 'clientB'

    def test_no_self_echo_in_received_audio(self, two_clients_and_relay):
        mw_a, mw_b, relay = two_clients_and_relay
        for _ in range(10):
            a_a = mw_a.capture_and_emit_audio()
            relay.relay_audio('clientA', a_a)
        assert len(mw_a.received_audio) == 0


# ---------------------------------------------------------------------------
# 4. Combined A/V — interleaved audio + video
# ---------------------------------------------------------------------------

class TestCombinedAVDelivery:
    """Interleaved audio and video from both clients."""

    def test_interleaved_av_delivery(self, two_clients_and_relay):
        mw_a, mw_b, relay = two_clients_and_relay

        for _ in range(10):
            # Video from both
            v_a = mw_a.capture_and_emit_video()
            relay.relay_video('clientA', v_a)
            v_b = mw_b.capture_and_emit_video()
            relay.relay_video('clientB', v_b)
            # Audio from both
            a_a = mw_a.capture_and_emit_audio()
            relay.relay_audio('clientA', a_a)
            a_b = mw_b.capture_and_emit_audio()
            relay.relay_audio('clientB', a_b)

        # Video assertions
        assert len(mw_b.received_video) == 10
        assert len(mw_a.received_video) == 10

        # Audio assertions
        assert len(mw_b.received_audio) == 10
        assert len(mw_a.received_audio) == 10

        # Verify ordering is maintained independently for each stream
        for i in range(10):
            vid_frame = np.array(mw_b.received_video[i]['frame'], dtype=np.uint8)
            assert MockFrameSource.frame_id(vid_frame) == i

            aud_chunk = np.array(mw_b.received_audio[i]['audio'], dtype=np.float32)
            assert MockAudioSource.chunk_id(aud_chunk) == i

    def test_tolist_roundtrip_preserves_audio_identity(self):
        """chunk.tolist() → np.array() roundtrip preserves chunk_id."""
        src = MockAudioSource(sample_rate=8196, frames_per_buffer=1366)
        for expected_id in range(10):
            chunk = src.capture()
            serialized = chunk.tolist()
            deserialized = np.array(serialized, dtype=np.float32)
            assert MockAudioSource.chunk_id(deserialized) == expected_id


# ---------------------------------------------------------------------------
# 5. Full lifecycle: register → connect → stream → disconnect → cleanup
# ---------------------------------------------------------------------------

class TestFullLifecycle:
    """Simulate the complete call lifecycle end-to-end."""

    def test_complete_call_lifecycle(self, mock_server):
        """
        1. Register two users
        2. Connect them
        3. Stream 10 video + 10 audio frames each way
        4. Verify all received intact
        5. Disconnect
        6. Verify server state is clean
        """
        from utils.user import UserState

        # Step 1: Register
        uid_a = mock_server.add_user(('127.0.0.1', 5001))
        uid_b = mock_server.add_user(('127.0.0.1', 5002))

        # Step 2: Connect
        mock_server.set_user_state(uid_a, UserState.CONNECTED, peer=uid_b)
        mock_server.set_user_state(uid_b, UserState.CONNECTED, peer=uid_a)

        # Step 3: Stream
        mw_a = MockMiddleware(uid_a, width=8, height=6)
        mw_b = MockMiddleware(uid_b, width=8, height=6)
        relay = MockSocketAPIRelay([mw_a, mw_b])

        for _ in range(10):
            # Video
            v_a = mw_a.capture_and_emit_video()
            relay.relay_video(uid_a, v_a)
            v_b = mw_b.capture_and_emit_video()
            relay.relay_video(uid_b, v_b)
            # Audio
            a_a = mw_a.capture_and_emit_audio()
            relay.relay_audio(uid_a, a_a)
            a_b = mw_b.capture_and_emit_audio()
            relay.relay_audio(uid_b, a_b)

        # Step 4: Verify
        assert len(mw_b.received_video) == 10
        assert len(mw_a.received_video) == 10
        assert len(mw_b.received_audio) == 10
        assert len(mw_a.received_audio) == 10

        for i in range(10):
            # B received A's video/audio
            vid = np.array(mw_b.received_video[i]['frame'], dtype=np.uint8)
            assert MockFrameSource.frame_id(vid) == i
            aud = np.array(mw_b.received_audio[i]['audio'], dtype=np.float32)
            assert MockAudioSource.chunk_id(aud) == i

            # A received B's video/audio
            vid = np.array(mw_a.received_video[i]['frame'], dtype=np.uint8)
            assert MockFrameSource.frame_id(vid) == i
            aud = np.array(mw_a.received_audio[i]['audio'], dtype=np.float32)
            assert MockAudioSource.chunk_id(aud) == i

        # Step 5: Disconnect
        mock_server.contact_client = MagicMock()
        mock_server.disconnect_peer(uid_a)

        # Step 6: Verify cleanup
        assert mock_server.get_user(uid_a).state == UserState.IDLE
        assert mock_server.get_user(uid_b).state == UserState.IDLE
        assert mock_server.get_user(uid_a).peer is None
        assert mock_server.get_user(uid_b).peer is None

    def test_server_clean_after_remove(self, mock_server):
        """After removing both users, the server has 0 users."""
        uid_a = mock_server.add_user(('127.0.0.1', 5001))
        uid_b = mock_server.add_user(('127.0.0.1', 5002))

        mock_server.remove_user(uid_a)
        mock_server.remove_user(uid_b)

        all_users = mock_server.user_manager.get_all_users()
        assert len(all_users) == 0
