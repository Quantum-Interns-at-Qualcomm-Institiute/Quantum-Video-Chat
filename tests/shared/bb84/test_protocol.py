"""Tests for the BB84 protocol engine."""
import pytest

from shared.bb84.physical_layer import ChannelParameters, Basis
from shared.bb84.protocol import (
    BB84Protocol, BB84ProtocolConfig, EavesdropperSimulator,
    BB84RoundResult,
)
from shared.bb84.utils import binary_entropy


class TestBinaryEntropy:
    def test_h_zero(self):
        assert binary_entropy(0.0) == 0.0

    def test_h_one(self):
        assert binary_entropy(1.0) == 0.0

    def test_h_half(self):
        assert abs(binary_entropy(0.5) - 1.0) < 1e-10

    def test_h_0_11(self):
        # h(0.11) ≈ 0.5
        h = binary_entropy(0.11)
        assert 0.48 < h < 0.52


class TestBB84Protocol:
    @pytest.fixture
    def ideal_config(self):
        """Config with high detection rate for reliable testing."""
        return BB84ProtocolConfig(
            num_raw_bits=8192,
            qber_threshold=0.11,
            target_key_length_bits=128,
            channel_params=ChannelParameters(
                source_intensity_mu=5.0,  # Many photons
                fiber_length_km=0.0,
                detector_efficiency=1.0,
                dark_count_rate=0.0,
                dead_time_ns=0.0,
                afterpulse_probability=0.0,
                misalignment_angle_deg=0.0,
            ),
        )

    @pytest.fixture
    def realistic_config(self):
        """Config modeling a realistic lab setup."""
        return BB84ProtocolConfig(
            num_raw_bits=16384,
            qber_threshold=0.11,
            target_key_length_bits=128,
            channel_params=ChannelParameters(
                source_intensity_mu=0.1,
                fiber_length_km=1.0,
                detector_efficiency=0.10,
                dark_count_rate=1e-5,
            ),
        )

    def test_successful_round_no_eavesdropper(self, ideal_config):
        protocol = BB84Protocol(ideal_config, seed=42)
        result = protocol.run_round()
        assert not result.aborted
        assert result.key is not None
        assert len(result.key) > 0
        assert result.qber < 0.11
        assert result.is_secure

    def test_sifting_rate_approximately_50_percent(self, ideal_config):
        protocol = BB84Protocol(ideal_config, seed=42)
        result = protocol.run_round()
        sifting_rate = result.sifted_bits / result.raw_bits_generated
        # Sifted bits should be roughly 50% of detected bits
        assert 0.3 < sifting_rate < 0.7

    def test_low_qber_without_eavesdropper(self, ideal_config):
        protocol = BB84Protocol(ideal_config, seed=42)
        result = protocol.run_round()
        assert result.qber < 0.05, f"QBER {result.qber} too high without Eve"

    def test_eavesdropper_raises_qber(self, ideal_config):
        protocol = BB84Protocol(ideal_config, seed=42)
        eve = EavesdropperSimulator(interception_rate=1.0, seed=123)
        result = protocol.run_round(eavesdropper=eve)
        # Full intercept-resend should give QBER ≈ 25%
        assert result.qber > 0.11, f"QBER {result.qber} should exceed threshold with Eve"
        assert result.aborted

    def test_partial_eavesdropper(self, ideal_config):
        protocol = BB84Protocol(ideal_config, seed=42)
        eve = EavesdropperSimulator(interception_rate=0.5, seed=123)
        result = protocol.run_round(eavesdropper=eve)
        # 50% interception should give QBER ≈ 12.5%
        assert result.qber > 0.05

    def test_key_length_correct(self, ideal_config):
        ideal_config.target_key_length_bits = 128
        protocol = BB84Protocol(ideal_config, seed=42)
        result = protocol.run_round()
        if not result.aborted and result.key:
            assert len(result.key) * 8 >= 64  # May be shorter due to PA

    def test_round_result_fields(self, ideal_config):
        protocol = BB84Protocol(ideal_config, seed=42)
        result = protocol.run_round()
        assert isinstance(result, BB84RoundResult)
        assert result.raw_bits_generated == ideal_config.num_raw_bits
        assert result.sifted_bits >= 0
        assert result.duration_seconds >= 0
        assert isinstance(result.qber, float)

    def test_realistic_config_produces_key(self, realistic_config):
        protocol = BB84Protocol(realistic_config, seed=42)
        result = protocol.run_round()
        # With realistic parameters, we may not always get a key
        # but with 16k raw bits we should get enough sifted bits
        if result.sifted_bits > 256:
            assert not result.aborted or result.qber >= 0.11

    def test_aborted_round_returns_none_key(self, ideal_config):
        protocol = BB84Protocol(ideal_config, seed=42)
        eve = EavesdropperSimulator(interception_rate=1.0, seed=123)
        result = protocol.run_round(eavesdropper=eve)
        if result.aborted:
            assert result.key is None
            assert result.abort_reason is not None


class TestEavesdropperSimulator:
    def test_correct_basis_match(self):
        eve = EavesdropperSimulator(seed=42)
        # Run many trials
        correct = 0
        total = 1000
        for _ in range(total):
            bit, basis = eve.intercept_resend(0, Basis.RECTILINEAR)
            if basis == Basis.RECTILINEAR:
                correct += 1
        # Eve picks basis randomly, so ~50% should match
        assert 400 < correct < 600

    def test_wrong_basis_random_bit(self):
        eve = EavesdropperSimulator(seed=42)
        bits_when_wrong = []
        for _ in range(1000):
            bit, basis = eve.intercept_resend(0, Basis.RECTILINEAR)
            if basis != Basis.RECTILINEAR:
                bits_when_wrong.append(bit)
        # Wrong-basis bits should be random
        if bits_when_wrong:
            zero_frac = sum(1 for b in bits_when_wrong if b == 0) / len(bits_when_wrong)
            assert 0.4 < zero_frac < 0.6
