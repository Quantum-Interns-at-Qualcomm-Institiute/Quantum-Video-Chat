"""
Unit tests for AudioSource classes — SilenceSource, MockAudioSource.

Verifies:
  1. SilenceSource produces zero-filled chunks
  2. MockAudioSource produces exactly 10 chunks, then None
  3. Each chunk is a pure sine wave at the correct frequency
  4. chunk_id() correctly identifies each chunk via FFT
  5. reset() allows re-emission
  6. Two independent sources produce identical sequences
  7. Looping mode auto-resets after exhaustion
"""
import numpy as np
import pytest

from shared.frame_source import SilenceSource, MockAudioSource


SAMPLE_RATE = 8196
FRAMES_PER_BUFFER = SAMPLE_RATE // 6  # 1366


class TestSilenceSource:
    """SilenceSource produces all-zero audio chunks."""

    def test_returns_zeros(self):
        src = SilenceSource(frames_per_buffer=100)
        chunk = src.capture()
        assert chunk is not None
        assert len(chunk) == 100
        assert np.all(chunk == 0.0)

    def test_dtype_is_float32(self):
        src = SilenceSource(frames_per_buffer=50)
        chunk = src.capture()
        assert chunk.dtype == np.float32

    def test_never_returns_none(self):
        src = SilenceSource(frames_per_buffer=50)
        for _ in range(20):
            assert src.capture() is not None

    def test_release_is_no_op(self):
        src = SilenceSource()
        src.release()  # should not raise


class TestMockAudioSourceBasics:
    """Core contract: 10 deterministic chunks, then None."""

    def test_produces_exactly_10_chunks(self):
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        chunks = []
        for _ in range(15):
            c = src.capture()
            if c is None:
                break
            chunks.append(c)
        assert len(chunks) == 10

    def test_returns_none_after_exhaustion(self):
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        for _ in range(10):
            src.capture()
        assert src.capture() is None
        assert src.capture() is None

    def test_chunk_length(self):
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        chunk = src.capture()
        assert len(chunk) == FRAMES_PER_BUFFER

    def test_chunk_dtype(self):
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        chunk = src.capture()
        assert chunk.dtype == np.float32

    def test_chunks_emitted_counter(self):
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        assert src.chunks_emitted == 0
        for i in range(1, 11):
            src.capture()
            assert src.chunks_emitted == i


class TestMockAudioSourceFrequencies:
    """Each chunk N has frequency (N+1) * BASE_FREQ Hz."""

    def test_each_chunk_has_correct_frequency(self):
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        for i in range(10):
            chunk = src.capture()
            expected_freq = (i + 1) * MockAudioSource.BASE_FREQ
            # Use FFT to find dominant frequency
            fft_mag = np.abs(np.fft.rfft(chunk))
            freqs = np.fft.rfftfreq(len(chunk), d=1.0 / SAMPLE_RATE)
            dominant_freq = freqs[np.argmax(fft_mag)]
            # Allow for FFT bin resolution (~6 Hz)
            assert abs(dominant_freq - expected_freq) < 10, (
                f"Chunk {i}: expected ~{expected_freq} Hz, got {dominant_freq:.1f} Hz"
            )

    def test_chunks_are_distinct(self):
        """Each chunk has a different dominant frequency."""
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        frequencies = []
        for _ in range(10):
            chunk = src.capture()
            fft_mag = np.abs(np.fft.rfft(chunk))
            freqs = np.fft.rfftfreq(len(chunk), d=1.0 / SAMPLE_RATE)
            frequencies.append(freqs[np.argmax(fft_mag)])
        # All should be distinct (within reasonable tolerance)
        for i in range(10):
            for j in range(i + 1, 10):
                assert abs(frequencies[i] - frequencies[j]) > 100


class TestChunkId:
    """chunk_id() extracts the sequence number from a mock audio chunk."""

    def test_identifies_all_10_chunks(self):
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        for expected_id in range(10):
            chunk = src.capture()
            assert MockAudioSource.chunk_id(
                chunk, SAMPLE_RATE, FRAMES_PER_BUFFER
            ) == expected_id

    def test_rejects_silence(self):
        chunk = np.zeros(FRAMES_PER_BUFFER, dtype=np.float32)
        result = MockAudioSource.chunk_id(chunk, SAMPLE_RATE, FRAMES_PER_BUFFER)
        # DC component (0 Hz) doesn't map to any valid chunk
        assert result == -1

    def test_rejects_wrong_frequency(self):
        """A sine wave at a non-BASE_FREQ-multiple frequency should be rejected."""
        t = np.arange(FRAMES_PER_BUFFER, dtype=np.float32) / SAMPLE_RATE
        # 3100 Hz doesn't match any (N+1)*200 pattern (closest is 3000 or 3200)
        chunk = np.sin(2 * np.pi * 3100 * t).astype(np.float32)
        result = MockAudioSource.chunk_id(chunk, SAMPLE_RATE, FRAMES_PER_BUFFER)
        assert result == -1


class TestMockAudioSourceReset:
    """reset() lets the source re-emit all 10 chunks."""

    def test_reset_replays_sequence(self):
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        first_pass = [src.capture().copy() for _ in range(10)]
        assert src.capture() is None

        src.reset()
        assert src.chunks_emitted == 0

        second_pass = [src.capture().copy() for _ in range(10)]
        for i in range(10):
            assert np.array_equal(first_pass[i], second_pass[i])


class TestMockAudioSourceLooping:
    """Looping mode auto-resets after the 10th chunk."""

    def test_looping_produces_more_than_10(self):
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
            looping=True,
        )
        chunks = [src.capture() for _ in range(25)]
        assert all(c is not None for c in chunks)

    def test_looping_repeats_sequence(self):
        src = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
            looping=True,
        )
        ids = []
        for _ in range(20):
            chunk = src.capture()
            ids.append(MockAudioSource.chunk_id(
                chunk, SAMPLE_RATE, FRAMES_PER_BUFFER
            ))
        assert ids == list(range(10)) + list(range(10))


class TestTwoAudioSourcesIdentical:
    """Two independent MockAudioSource instances produce the same sequence."""

    def test_identical_sequences(self):
        src_a = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        src_b = MockAudioSource(
            sample_rate=SAMPLE_RATE,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        for _ in range(10):
            ca = src_a.capture()
            cb = src_b.capture()
            assert np.array_equal(ca, cb)
