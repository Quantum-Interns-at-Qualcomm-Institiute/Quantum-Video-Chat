"""Tests for the BB84KeyGenerator."""
import pytest

from shared.bb84.physical_layer import ChannelParameters
from shared.bb84.protocol import BB84ProtocolConfig, EavesdropperSimulator
from shared.encryption import (
    AbstractKeyGenerator,
    BB84KeyGenerator,
    create_key_generator,
)


@pytest.fixture
def ideal_config():
    return BB84ProtocolConfig(
        num_raw_bits=8192,
        target_key_length_bits=128,
        channel_params=ChannelParameters(
            source_intensity_mu=5.0,
            fiber_length_km=0.0,
            detector_efficiency=1.0,
            dark_count_rate=0.0,
            dead_time_ns=0.0,
            afterpulse_probability=0.0,
            misalignment_angle_deg=0.0,
        ),
    )


class TestBB84KeyGenerator:
    def test_implements_interface(self):
        gen = BB84KeyGenerator()
        assert isinstance(gen, AbstractKeyGenerator)

    def test_registry_lookup(self):
        gen = create_key_generator("BB84")
        assert isinstance(gen, BB84KeyGenerator)

    def test_generate_key_produces_bytes(self, ideal_config):
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.generate_key(key_length=128)
        key = gen.get_key()
        assert isinstance(key, bytes)
        assert len(key) > 0

    def test_last_round_result_available(self, ideal_config):
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.generate_key(key_length=128)
        result = gen.last_round_result
        assert result is not None
        assert hasattr(result, "qber")
        assert hasattr(result, "aborted")

    def test_eavesdropper_causes_abort(self, ideal_config):
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.generate_key(key_length=128)
        old_key = gen.get_key()

        eve = EavesdropperSimulator(interception_rate=1.0, seed=123)
        gen.set_eavesdropper(eve)
        gen.generate_key(key_length=128)

        result = gen.last_round_result
        assert result.aborted
        # Key should not have changed (kept old key)
        assert gen.get_key() == old_key

    def test_clear_eavesdropper(self, ideal_config):
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        eve = EavesdropperSimulator(interception_rate=1.0)
        gen.set_eavesdropper(eve)
        gen.clear_eavesdropper()
        gen.generate_key(key_length=128)
        # Should succeed without eavesdropper
        result = gen.last_round_result
        if result.sifted_bits > 256:
            assert not result.aborted

    def test_metrics_callback_called(self, ideal_config):
        results = []
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.set_metrics_callback(results.append)
        gen.generate_key(key_length=128)
        assert len(results) == 1
        assert results[0].raw_bits_generated == ideal_config.num_raw_bits
