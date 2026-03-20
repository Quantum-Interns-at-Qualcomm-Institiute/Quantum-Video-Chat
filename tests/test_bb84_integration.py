"""Integration tests for BB84 → encryption → video pipeline."""
import pytest

from shared.bb84.physical_layer import ChannelParameters
from shared.bb84.protocol import BB84Protocol, BB84ProtocolConfig, EavesdropperSimulator
from shared.bb84.qber_monitor import QBERMonitor, QBEREvent
from shared.encryption import (
    BB84KeyGenerator, AESEncryption,
    create_key_generator, create_encrypt_scheme,
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


class TestBB84ToAESRoundtrip:
    """Test that BB84-generated keys work with AES encryption."""

    def test_bb84_key_encrypts_decrypts(self, ideal_config):
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.generate_key(key_length=128)
        key = gen.get_key()

        assert key is not None
        assert len(key) >= 16

        aes = AESEncryption()
        plaintext = b'Hello, quantum world! This is a test message for AES.'

        # Use first 16 bytes of key for AES-128
        aes_key = key[:16]
        ciphertext = aes.encrypt(plaintext, aes_key)
        decrypted = aes.decrypt(ciphertext, aes_key)
        assert decrypted == plaintext

    def test_bb84_key_with_registry(self, ideal_config):
        gen = create_key_generator('BB84')
        assert isinstance(gen, BB84KeyGenerator)

        scheme = create_encrypt_scheme('AES')
        assert isinstance(scheme, AESEncryption)


class TestBB84QBERMonitorIntegration:
    """Test BB84 key generator feeding into QBER monitor."""

    def test_monitor_receives_round_results(self, ideal_config):
        monitor = QBERMonitor()
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.set_metrics_callback(monitor.record_round)

        gen.generate_key(key_length=128)

        history = monitor.get_history()
        assert len(history) == 1
        assert history[0].qber < 0.11

    def test_intrusion_detected_through_pipeline(self, ideal_config):
        monitor = QBERMonitor()
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.set_metrics_callback(monitor.record_round)

        # Normal round first
        gen.generate_key(key_length=128)
        assert not gen.last_round_result.aborted

        # Enable eavesdropper
        eve = EavesdropperSimulator(interception_rate=1.0, seed=42)
        gen.set_eavesdropper(eve)
        gen.generate_key(key_length=128)

        summary = monitor.get_summary()
        assert summary['intrusion_count'] >= 1

        # Check that the intrusion event was recorded
        history = monitor.get_history()
        intrusion_events = [s for s in history
                           if s.event == QBEREvent.INTRUSION_DETECTED]
        assert len(intrusion_events) >= 1

    def test_key_survives_intrusion(self, ideal_config):
        """Old key should remain usable during intrusion."""
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.generate_key(key_length=128)
        good_key = gen.get_key()

        eve = EavesdropperSimulator(interception_rate=1.0, seed=42)
        gen.set_eavesdropper(eve)
        gen.generate_key(key_length=128)

        # Key should not have changed
        assert gen.get_key() == good_key

        # Old key still works for encryption
        aes = AESEncryption()
        plaintext = b'Still encrypted during intrusion'
        aes_key = good_key[:16]
        ciphertext = aes.encrypt(plaintext, aes_key)
        assert aes.decrypt(ciphertext, aes_key) == plaintext

    def test_recovery_after_eavesdropper_removed(self, ideal_config):
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.generate_key(key_length=128)
        old_key = gen.get_key()

        # Enable then disable eavesdropper
        eve = EavesdropperSimulator(interception_rate=1.0, seed=42)
        gen.set_eavesdropper(eve)
        gen.generate_key(key_length=128)
        assert gen.get_key() == old_key  # Key unchanged during intrusion

        gen.clear_eavesdropper()
        gen.generate_key(key_length=128)

        if not gen.last_round_result.aborted:
            new_key = gen.get_key()
            assert new_key != old_key  # New key generated after recovery
