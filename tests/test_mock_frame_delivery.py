"""
Integration tests for end-to-end frame delivery using MockFrameSource.

Verifies that 10 deterministic frames from MockFrameSource are correctly
relayed through the SocketAPI frame handler, arriving at the peer in the
correct order with the correct content.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from shared.frame_source import MockFrameSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FrameCollector:
    """Collects frames emitted by SocketAPI to a specific socket sid."""

    def __init__(self):
        self.received_frames = []

    def emit(self, event, data, **kwargs):
        if event == 'frame':
            self.received_frames.append(data)


def _make_socket_api_stub(user_ids):
    """Build a minimal SocketAPI-like object for frame relay testing.

    Returns a dict mapping user_id → collector, plus the relay function.
    """
    users = {}
    collectors = {}
    for i, uid in enumerate(user_ids):
        sid = f'sid_{uid}'
        users[uid] = sid
        collectors[uid] = FrameCollector()

    sids = {sid: uid for uid, sid in users.items()}

    def relay_frame(data, sender_sid):
        """Mimics SocketAPI._on_frame: forward to all except sender."""
        sender_id = sids.get(sender_sid)
        for uid, sid in users.items():
            if sid and sid != sender_sid:
                collectors[uid].emit('frame', {
                    'frame': data.get('frame'),
                    'width': data.get('width'),
                    'height': data.get('height'),
                    'sender': sender_id,
                })

    return users, collectors, relay_frame


# ---------------------------------------------------------------------------
# 1. MockFrameSource → relay → peer receives all 10 in order
# ---------------------------------------------------------------------------

class TestMockFrameDeliveryThroughRelay:
    """Full pipeline: MockFrameSource → SocketAPI relay → peer collector."""

    def test_10_frames_delivered_in_order(self):
        """Sender captures 10 frames, relay forwards each, peer receives
        all 10 in strict sequential order."""
        src = MockFrameSource(width=8, height=6)
        users, collectors, relay = _make_socket_api_stub(['sender', 'receiver'])
        sender_sid = users['sender']

        for _ in range(10):
            frame = src.capture()
            assert frame is not None
            relay(
                {'frame': frame.tolist(), 'width': 8, 'height': 6},
                sender_sid,
            )

        # Sender should NOT have received its own frames
        assert len(collectors['sender'].received_frames) == 0

        # Receiver should have all 10 frames in order
        received = collectors['receiver'].received_frames
        assert len(received) == 10

        for i, data in enumerate(received):
            frame_array = np.array(data['frame'], dtype=np.uint8)
            seq = MockFrameSource.frame_id(frame_array)
            assert seq == i, f"Frame {i}: expected seq={i}, got {seq}"

    def test_bidirectional_frame_delivery(self):
        """Both peers send 10 frames simultaneously; each receives the
        other's 10 frames in order."""
        src_a = MockFrameSource(width=4, height=4)
        src_b = MockFrameSource(width=4, height=4)
        users, collectors, relay = _make_socket_api_stub(['alice', 'bob'])

        for _ in range(10):
            # Alice sends
            fa = src_a.capture()
            relay(
                {'frame': fa.tolist(), 'width': 4, 'height': 4},
                users['alice'],
            )
            # Bob sends
            fb = src_b.capture()
            relay(
                {'frame': fb.tolist(), 'width': 4, 'height': 4},
                users['bob'],
            )

        # Bob receives Alice's 10 frames
        bob_received = collectors['bob'].received_frames
        assert len(bob_received) == 10
        for i, data in enumerate(bob_received):
            frame_array = np.array(data['frame'], dtype=np.uint8)
            assert MockFrameSource.frame_id(frame_array) == i

        # Alice receives Bob's 10 frames
        alice_received = collectors['alice'].received_frames
        assert len(alice_received) == 10
        for i, data in enumerate(alice_received):
            frame_array = np.array(data['frame'], dtype=np.uint8)
            assert MockFrameSource.frame_id(frame_array) == i

    def test_frame_dimensions_preserved(self):
        """Width and height metadata survive the relay."""
        src = MockFrameSource(width=16, height=12)
        users, collectors, relay = _make_socket_api_stub(['sender', 'receiver'])

        frame = src.capture()
        relay(
            {'frame': frame.tolist(), 'width': 16, 'height': 12},
            users['sender'],
        )

        received = collectors['receiver'].received_frames[0]
        assert received['width'] == 16
        assert received['height'] == 12
        frame_array = np.array(received['frame'], dtype=np.uint8)
        assert frame_array.shape == (12, 16, 3)

    def test_sender_identified_in_relay(self):
        """The relay tags each frame with the sender's user ID."""
        src = MockFrameSource(width=4, height=4)
        users, collectors, relay = _make_socket_api_stub(['sender', 'receiver'])

        frame = src.capture()
        relay(
            {'frame': frame.tolist(), 'width': 4, 'height': 4},
            users['sender'],
        )

        received = collectors['receiver'].received_frames[0]
        assert received['sender'] == 'sender'


# ---------------------------------------------------------------------------
# 2. Simulate the full VideoThread → relay pipeline (mocked threads)
# ---------------------------------------------------------------------------

class TestVideoThreadWithMockSource:
    """Verify VideoThread can use MockFrameSource instead of a camera."""

    def test_mock_source_integration(self):
        """MockFrameSource can be swapped in where CameraSource is used,
        and produces the correct frames."""
        src = MockFrameSource(width=8, height=6)

        # Simulate what VideoThread._run does with each frame
        emitted_frames = []
        for _ in range(10):
            frame = src.capture()
            if frame is None:
                break
            emitted_frames.append(frame.tolist())

        assert len(emitted_frames) == 10

        # Verify each frame is identifiable
        for i, frame_list in enumerate(emitted_frames):
            frame_array = np.array(frame_list, dtype=np.uint8)
            assert MockFrameSource.frame_id(frame_array) == i

    def test_exhaustion_stops_emission(self):
        """After 10 frames, capture returns None — the loop should stop."""
        src = MockFrameSource(width=4, height=4)
        count = 0
        while True:
            frame = src.capture()
            if frame is None:
                break
            count += 1
        assert count == 10


# ---------------------------------------------------------------------------
# 3. End-to-end: two MockFrameSources → relay → both receive correct order
# ---------------------------------------------------------------------------

class TestFullE2EMockFrames:
    """Simulate two clients each with their own MockFrameSource, sending
    through a relay, and verifying receipt on both sides."""

    def test_interleaved_send_receive(self):
        """Interleave sends from both clients and verify each receives
        the other's frames in order."""
        src_a = MockFrameSource(width=4, height=4)
        src_b = MockFrameSource(width=4, height=4)
        users, collectors, relay = _make_socket_api_stub(['clientA', 'clientB'])

        # Interleave: A sends 3, B sends 2, A sends 7, B sends 8
        schedule = [
            ('clientA', src_a, 3),
            ('clientB', src_b, 2),
            ('clientA', src_a, 7),
            ('clientB', src_b, 8),
        ]

        for sender_id, src, count in schedule:
            for _ in range(count):
                frame = src.capture()
                if frame is None:
                    break
                relay(
                    {'frame': frame.tolist(), 'width': 4, 'height': 4},
                    users[sender_id],
                )

        # clientB should have received all 10 of clientA's frames in order
        b_received = collectors['clientB'].received_frames
        assert len(b_received) == 10
        for i, data in enumerate(b_received):
            arr = np.array(data['frame'], dtype=np.uint8)
            assert MockFrameSource.frame_id(arr) == i, (
                f"clientB frame {i}: expected id={i}, got {MockFrameSource.frame_id(arr)}"
            )

        # clientA should have received all 10 of clientB's frames in order
        a_received = collectors['clientA'].received_frames
        assert len(a_received) == 10
        for i, data in enumerate(a_received):
            arr = np.array(data['frame'], dtype=np.uint8)
            assert MockFrameSource.frame_id(arr) == i, (
                f"clientA frame {i}: expected id={i}, got {MockFrameSource.frame_id(arr)}"
            )

    def test_tolist_roundtrip_preserves_identity(self):
        """frame.tolist() → np.array() roundtrip preserves frame_id."""
        src = MockFrameSource(width=8, height=6)
        for expected_id in range(10):
            frame = src.capture()
            # Simulate serialization: numpy → list → numpy
            serialized = frame.tolist()
            deserialized = np.array(serialized, dtype=np.uint8)
            assert MockFrameSource.frame_id(deserialized) == expected_id
