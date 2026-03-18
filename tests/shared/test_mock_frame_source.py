"""
Unit tests for MockFrameSource — deterministic test frame generation.

Verifies:
  1. Produces exactly 10 frames, then None
  2. Each frame has the correct uniform pixel value
  3. frame_id() correctly identifies each frame
  4. reset() allows re-emission
  5. Two independent sources produce identical sequences
  6. Frames arrive in strict sequential order
"""
import numpy as np
import pytest

from shared.frame_source import MockFrameSource


class TestMockFrameSourceBasics:
    """Core contract: 10 deterministic frames, then None."""

    def test_produces_exactly_10_frames(self):
        src = MockFrameSource(width=4, height=4)
        frames = []
        for _ in range(15):
            f = src.capture()
            if f is None:
                break
            frames.append(f)
        assert len(frames) == 10

    def test_returns_none_after_exhaustion(self):
        src = MockFrameSource(width=4, height=4)
        for _ in range(10):
            src.capture()
        assert src.capture() is None
        assert src.capture() is None  # stays None

    def test_frame_dimensions(self):
        src = MockFrameSource(width=16, height=8)
        frame = src.capture()
        assert frame.shape == (8, 16, 3)

    def test_frame_dtype(self):
        src = MockFrameSource(width=4, height=4)
        frame = src.capture()
        assert frame.dtype == np.uint8


class TestMockFrameSourceValues:
    """Each frame N has all pixels set to N * 25."""

    def test_each_frame_has_correct_value(self):
        src = MockFrameSource(width=4, height=4)
        for i in range(10):
            frame = src.capture()
            expected_value = i * 25
            assert np.all(frame == expected_value), (
                f"Frame {i}: expected all pixels = {expected_value}, "
                f"got min={frame.min()}, max={frame.max()}"
            )

    def test_frames_are_visually_distinct(self):
        src = MockFrameSource(width=4, height=4)
        frames = [src.capture() for _ in range(10)]
        for i in range(10):
            for j in range(i + 1, 10):
                assert not np.array_equal(frames[i], frames[j]), (
                    f"Frames {i} and {j} should be distinct"
                )


class TestFrameId:
    """frame_id() extracts the sequence number from a mock frame."""

    def test_identifies_all_10_frames(self):
        src = MockFrameSource(width=8, height=8)
        for expected_id in range(10):
            frame = src.capture()
            assert MockFrameSource.frame_id(frame) == expected_id

    def test_rejects_non_uniform_frame(self):
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        frame[0, 0, 0] = 50  # matches step but not uniform
        assert MockFrameSource.frame_id(frame) == -1

    def test_rejects_non_step_value(self):
        frame = np.full((4, 4, 3), 17, dtype=np.uint8)  # 17 % 25 != 0
        assert MockFrameSource.frame_id(frame) == -1

    def test_rejects_out_of_range(self):
        frame = np.full((4, 4, 3), 250, dtype=np.uint8)  # 250/25 = 10, >= NUM_FRAMES
        assert MockFrameSource.frame_id(frame) == -1


class TestReset:
    """reset() lets the source re-emit all 10 frames."""

    def test_reset_replays_sequence(self):
        src = MockFrameSource(width=4, height=4)
        first_pass = [src.capture().copy() for _ in range(10)]
        assert src.capture() is None

        src.reset()
        assert src.frames_emitted == 0

        second_pass = [src.capture().copy() for _ in range(10)]
        for i in range(10):
            assert np.array_equal(first_pass[i], second_pass[i])


class TestTwoSourcesIdentical:
    """Two independent MockFrameSource instances produce the same sequence."""

    def test_identical_sequences(self):
        src_a = MockFrameSource(width=8, height=6)
        src_b = MockFrameSource(width=8, height=6)
        for _ in range(10):
            fa = src_a.capture()
            fb = src_b.capture()
            assert np.array_equal(fa, fb)


class TestSequentialOrder:
    """Verify frames arrive in strictly ascending order by ID."""

    def test_sequential_ids(self):
        src = MockFrameSource(width=4, height=4)
        ids = []
        while True:
            f = src.capture()
            if f is None:
                break
            ids.append(MockFrameSource.frame_id(f))
        assert ids == list(range(10))

    def test_frames_emitted_counter(self):
        src = MockFrameSource(width=4, height=4)
        assert src.frames_emitted == 0
        for i in range(1, 11):
            src.capture()
            assert src.frames_emitted == i
