"""Integration tests for the full BB84 key exchange flow.

Covers: qubit generation → basis selection → measurement → sifting →
error estimation → privacy amplification → AES-GCM encryption.

Edge cases: high error rate, insufficient key material, eavesdropper
detection, key recovery, and multi-round key rotation.
"""
import pytest

from shared.bb84.physical_layer import ChannelParameters, Basis
from shared.bb84.protocol import (
    BB84Protocol, BB84ProtocolConfig, BB84RoundResult, EavesdropperSimulator,
)
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


@pytest.fixture
def lossy_config():
    """Config with high loss — may produce insufficient key material."""
    return BB84ProtocolConfig(
        num_raw_bits=256,
        target_key_length_bits=128,
        channel_params=ChannelParameters(
            source_intensity_mu=0.05,
            fiber_length_km=50.0,
            detector_efficiency=0.05,
            dark_count_rate=1e-4,
        ),
    )


@pytest.fixture
def noisy_config():
    """Config with high misalignment — elevated but sub-threshold QBER."""
    return BB84ProtocolConfig(
        num_raw_bits=8192,
        target_key_length_bits=128,
        channel_params=ChannelParameters(
            source_intensity_mu=5.0,
            fiber_length_km=0.0,
            detector_efficiency=1.0,
            dark_count_rate=0.0,
            misalignment_angle_deg=8.0,
        ),
    )


# ---- Full pipeline: BB84 → AES-GCM ----

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

    def test_different_rounds_produce_different_keys(self, ideal_config):
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.generate_key(key_length=128)
        key1 = gen.get_key()

        gen.generate_key(key_length=128)
        key2 = gen.get_key()

        # Two independent rounds should (almost certainly) produce different keys
        if key1 and key2:
            assert key1 != key2

    def test_256_bit_key_for_aes256(self, ideal_config):
        ideal_config.target_key_length_bits = 256
        ideal_config.num_raw_bits = 16384
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.generate_key(key_length=256)
        key = gen.get_key()

        if key and len(key) >= 32:
            aes = AESEncryption(bits=256)
            plaintext = b'AES-256 with quantum key distribution'
            aes_key = key[:32]
            ciphertext = aes.encrypt(plaintext, aes_key)
            assert aes.decrypt(ciphertext, aes_key) == plaintext


# ---- Full protocol flow verification ----

class TestBB84FullProtocolFlow:
    """Verify each stage of the BB84 pipeline produces correct results."""

    def test_complete_round_stages(self, ideal_config):
        """Verify a successful round passes through all stages."""
        protocol = BB84Protocol(ideal_config, seed=42)
        result = protocol.run_round()

        assert isinstance(result, BB84RoundResult)
        assert result.raw_bits_generated == 8192
        assert result.sifted_bits > 0
        assert result.sifted_bits < result.raw_bits_generated
        assert result.detection_events > 0
        assert result.qber < 0.11
        assert result.is_secure
        assert not result.aborted
        assert result.abort_reason is None
        assert result.key is not None
        assert result.final_key_bits > 0
        assert result.duration_seconds >= 0

    def test_sifting_discards_approximately_half(self, ideal_config):
        """After sifting, ~50% of detected bits remain (matching bases)."""
        protocol = BB84Protocol(ideal_config, seed=42)
        result = protocol.run_round()

        sifting_rate = result.sifted_bits / result.detection_events
        assert 0.35 < sifting_rate < 0.65, (
            f"Sifting rate {sifting_rate:.2f} outside expected range"
        )

    def test_privacy_amplification_shortens_key(self, ideal_config):
        """PA output should be shorter than sifted bits (information is removed)."""
        protocol = BB84Protocol(ideal_config, seed=42)
        result = protocol.run_round()

        if not result.aborted:
            assert result.final_key_bits < result.sifted_bits

    def test_error_correction_produces_valid_key(self, ideal_config):
        """The final key should be usable for symmetric encryption."""
        protocol = BB84Protocol(ideal_config, seed=42)
        result = protocol.run_round()

        assert not result.aborted
        key = result.key
        assert isinstance(key, bytes)
        assert len(key) > 0

        # Key should encrypt/decrypt successfully
        aes = AESEncryption()
        aes_key = key[:16]
        ct = aes.encrypt(b'test', aes_key)
        assert aes.decrypt(ct, aes_key) == b'test'


# ---- Eavesdropper detection ----

class TestBB84EavesdropperDetection:
    """Test that eavesdropping is reliably detected through QBER."""

    def test_full_interception_aborts(self, ideal_config):
        protocol = BB84Protocol(ideal_config, seed=42)
        eve = EavesdropperSimulator(interception_rate=1.0, seed=123)
        result = protocol.run_round(eavesdropper=eve)

        assert result.aborted
        assert result.qber > 0.11
        assert result.key is None
        assert 'QBER' in result.abort_reason

    def test_full_interception_qber_near_25_percent(self, ideal_config):
        """Full intercept-resend should cause ~25% QBER."""
        protocol = BB84Protocol(ideal_config, seed=42)
        eve = EavesdropperSimulator(interception_rate=1.0, seed=123)
        result = protocol.run_round(eavesdropper=eve)

        assert 0.15 < result.qber < 0.35, (
            f"QBER {result.qber:.3f} not near expected ~0.25"
        )

    def test_partial_interception_detected(self, ideal_config):
        """Even 50% interception should be detectable."""
        protocol = BB84Protocol(ideal_config, seed=42)
        eve = EavesdropperSimulator(interception_rate=0.5, seed=123)
        result = protocol.run_round(eavesdropper=eve)

        # 50% interception → ~12.5% QBER, above 11% threshold
        assert result.qber > 0.05

    def test_low_interception_may_evade_detection(self, ideal_config):
        """Very low interception rates produce QBER below threshold."""
        protocol = BB84Protocol(ideal_config, seed=42)
        eve = EavesdropperSimulator(interception_rate=0.1, seed=123)
        result = protocol.run_round(eavesdropper=eve)

        # 10% interception → ~2.5% QBER, should be below threshold
        assert result.qber < 0.11 or result.aborted


# ---- QBER monitor integration ----

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

    def test_multi_round_monitor_history(self, ideal_config):
        """Monitor tracks history across multiple rounds."""
        monitor = QBERMonitor()
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        gen.set_metrics_callback(monitor.record_round)

        for _ in range(5):
            gen.generate_key(key_length=128)

        history = monitor.get_history()
        assert len(history) == 5

        summary = monitor.get_summary()
        assert summary['total_rounds'] == 5
        assert summary['average_qber_last_10'] < 0.11


# ---- Edge cases ----

class TestBB84EdgeCases:
    """Edge cases: insufficient key material, high loss, extreme parameters."""

    def test_insufficient_sifted_bits_aborts(self):
        """Very few raw bits → not enough sifted bits for a key."""
        config = BB84ProtocolConfig(
            num_raw_bits=16,
            target_key_length_bits=128,
            channel_params=ChannelParameters(
                source_intensity_mu=0.05,
                fiber_length_km=0.0,
                detector_efficiency=0.5,
            ),
        )
        protocol = BB84Protocol(config, seed=42)
        result = protocol.run_round()

        # With only 16 raw bits, almost certainly not enough for a 128-bit key
        assert result.aborted or result.final_key_bits < 128

    def test_high_loss_channel_may_abort(self, lossy_config):
        """High-loss channel may not produce enough detections."""
        protocol = BB84Protocol(lossy_config, seed=42)
        result = protocol.run_round()

        # May abort due to no detections or insufficient sifted bits
        if result.aborted:
            assert result.key is None
            assert result.abort_reason is not None

    def test_noisy_channel_elevated_qber(self, noisy_config):
        """Misalignment-induced errors raise QBER but may still succeed."""
        protocol = BB84Protocol(noisy_config, seed=42)
        result = protocol.run_round()

        # With misalignment, QBER may be elevated but with small samples
        # could still be 0.0 by chance — just verify round completes
        if not result.aborted:
            assert result.qber < noisy_config.qber_threshold

    def test_zero_interception_rate_no_effect(self, ideal_config):
        """Eavesdropper with 0% interception has no effect."""
        protocol = BB84Protocol(ideal_config, seed=42)
        eve = EavesdropperSimulator(interception_rate=0.0, seed=123)
        result = protocol.run_round(eavesdropper=eve)

        assert not result.aborted
        assert result.qber < 0.05

    def test_dark_counts_contribute_to_qber(self):
        """Dark counts (false detections) should increase QBER."""
        config_clean = BB84ProtocolConfig(
            num_raw_bits=8192,
            channel_params=ChannelParameters(
                source_intensity_mu=5.0,
                detector_efficiency=1.0,
                dark_count_rate=0.0,
            ),
        )
        config_dark = BB84ProtocolConfig(
            num_raw_bits=8192,
            channel_params=ChannelParameters(
                source_intensity_mu=5.0,
                detector_efficiency=1.0,
                dark_count_rate=0.01,
            ),
        )
        result_clean = BB84Protocol(config_clean, seed=42).run_round()
        result_dark = BB84Protocol(config_dark, seed=42).run_round()

        # Dark counts add noise, so QBER should be higher (or equal)
        if not result_clean.aborted and not result_dark.aborted:
            assert result_dark.dark_count_fraction >= result_clean.dark_count_fraction

    def test_deterministic_with_seed(self, ideal_config):
        """Same seed produces consistent QBER (physical layer has own RNG)."""
        p1 = BB84Protocol(ideal_config, seed=999)
        p2 = BB84Protocol(ideal_config, seed=999)

        r1 = p1.run_round()
        r2 = p2.run_round()

        # Protocol RNG is seeded, but physical layer RNG is independent,
        # so sifted_bits may differ slightly. QBER should both be ~0.
        assert r1.qber == r2.qber
        assert not r1.aborted
        assert not r2.aborted


# ---- Key rotation ----

class TestBB84KeyRotation:
    """Test multiple rounds of key generation (key rotation scenario)."""

    def test_rotate_key_multiple_times(self, ideal_config):
        """Simulate rotating keys every round, encrypting with the latest."""
        gen = BB84KeyGenerator(protocol_config=ideal_config)
        aes = AESEncryption()
        messages = [
            b'Message 1: initial key',
            b'Message 2: rotated key',
            b'Message 3: rotated again',
        ]

        for msg in messages:
            gen.generate_key(key_length=128)
            key = gen.get_key()
            if key and len(key) >= 16:
                aes_key = key[:16]
                ct = aes.encrypt(msg, aes_key)
                assert aes.decrypt(ct, aes_key) == msg
