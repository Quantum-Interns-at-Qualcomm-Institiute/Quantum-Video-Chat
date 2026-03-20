"""Tests for the BB84 physical layer simulation."""
import numpy as np
import pytest

from shared.bb84.physical_layer import (
    ChannelParameters, Basis, Polarization, DetectionEvent,
    PhotonSource, QuantumChannel, SinglePhotonDetector,
    PhysicalLayerSimulator,
)


class TestPhotonSource:
    def test_emits_poisson_distributed_photons(self):
        params = ChannelParameters(source_intensity_mu=0.5)
        source = PhotonSource(params, rng=np.random.default_rng(42))
        counts = [source.emit_pulse(0, Basis.RECTILINEAR)[0] for _ in range(10000)]
        mean = np.mean(counts)
        assert abs(mean - 0.5) < 0.05, f"Mean {mean} not close to mu=0.5"

    def test_low_mu_mostly_zero_photons(self):
        params = ChannelParameters(source_intensity_mu=0.1)
        source = PhotonSource(params, rng=np.random.default_rng(42))
        counts = [source.emit_pulse(0, Basis.RECTILINEAR)[0] for _ in range(10000)]
        zero_fraction = sum(1 for c in counts if c == 0) / len(counts)
        assert zero_fraction > 0.88, f"Zero fraction {zero_fraction} too low for mu=0.1"

    def test_correct_polarization_encoding(self):
        params = ChannelParameters()
        source = PhotonSource(params)
        _, pol = source.emit_pulse(0, Basis.RECTILINEAR)
        assert pol == Polarization.H
        _, pol = source.emit_pulse(1, Basis.RECTILINEAR)
        assert pol == Polarization.V
        _, pol = source.emit_pulse(0, Basis.DIAGONAL)
        assert pol == Polarization.D
        _, pol = source.emit_pulse(1, Basis.DIAGONAL)
        assert pol == Polarization.A


class TestQuantumChannel:
    def test_no_photons_pass_through_with_zero(self):
        params = ChannelParameters()
        channel = QuantumChannel(params)
        assert channel.transmit(0) == 0

    def test_attenuation_reduces_photon_count(self):
        params = ChannelParameters(fiber_length_km=10.0, attenuation_db_per_km=0.2)
        channel = QuantumChannel(params, rng=np.random.default_rng(42))
        # 10km * 0.2 dB/km = 2 dB loss, transmission ≈ 63%
        survived = [channel.transmit(100) for _ in range(1000)]
        mean_survived = np.mean(survived)
        expected = 100 * 10 ** (-2.0 / 10)  # ≈ 63
        assert abs(mean_survived - expected) < 5

    def test_zero_length_no_loss(self):
        params = ChannelParameters(fiber_length_km=0.0)
        channel = QuantumChannel(params, rng=np.random.default_rng(42))
        assert channel.transmit(10) == 10


class TestSinglePhotonDetector:
    def test_correct_basis_deterministic(self):
        params = ChannelParameters(
            detector_efficiency=1.0, dark_count_rate=0.0,
            afterpulse_probability=0.0, misalignment_angle_deg=0.0,
        )
        det = SinglePhotonDetector(params, rng=np.random.default_rng(42))
        event = det.detect(1, Polarization.H, Basis.RECTILINEAR, 0)
        assert event.detected
        assert event.measured_bit == 0

    def test_wrong_basis_random_outcome(self):
        params = ChannelParameters(
            detector_efficiency=1.0, dark_count_rate=0.0,
            afterpulse_probability=0.0, misalignment_angle_deg=0.0,
        )
        det = SinglePhotonDetector(params, rng=np.random.default_rng(42))
        results = []
        for i in range(1000):
            det.reset()
            event = det.detect(1, Polarization.H, Basis.DIAGONAL, i * 100)
            if event.detected:
                results.append(event.measured_bit)
        # Should be roughly 50/50
        zero_frac = sum(1 for r in results if r == 0) / len(results)
        assert 0.4 < zero_frac < 0.6, f"Wrong-basis not 50/50: {zero_frac}"

    def test_dark_counts(self):
        params = ChannelParameters(
            detector_efficiency=0.0, dark_count_rate=0.5,
            afterpulse_probability=0.0,
        )
        det = SinglePhotonDetector(params, rng=np.random.default_rng(42))
        detections = sum(
            1 for i in range(1000)
            if det.detect(0, Polarization.H, Basis.RECTILINEAR, i * 100).detected
        )
        # With 50% dark count rate and no photons, ~50% should detect
        assert 400 < detections < 600

    def test_detector_efficiency(self):
        params = ChannelParameters(
            detector_efficiency=0.5, dark_count_rate=0.0,
            afterpulse_probability=0.0,
        )
        det = SinglePhotonDetector(params, rng=np.random.default_rng(42))
        detections = sum(
            1 for i in range(1000)
            if det.detect(1, Polarization.H, Basis.RECTILINEAR, i * 100).detected
        )
        assert 400 < detections < 600


class TestPhysicalLayerSimulator:
    def test_simulate_single_pulse(self):
        sim = PhysicalLayerSimulator(seed=42)
        event = sim.simulate_pulse(0, Basis.RECTILINEAR, Basis.RECTILINEAR)
        assert isinstance(event, DetectionEvent)

    def test_simulate_n_pulses(self):
        sim = PhysicalLayerSimulator(seed=42)
        n = 100
        bits = [0] * n
        bases = [Basis.RECTILINEAR] * n
        events = sim.simulate_n_pulses(n, bits, bases, bases)
        assert len(events) == n
        assert all(isinstance(e, DetectionEvent) for e in events)

    def test_matching_bases_correct_bits(self):
        """With ideal parameters and matching bases, detected bits should match."""
        params = ChannelParameters(
            source_intensity_mu=10.0,  # Many photons to ensure detection
            fiber_length_km=0.0,
            detector_efficiency=1.0,
            dark_count_rate=0.0,
            afterpulse_probability=0.0,
            misalignment_angle_deg=0.0,
        )
        sim = PhysicalLayerSimulator(params, seed=42)
        n = 100
        bits = [i % 2 for i in range(n)]
        bases = [Basis.RECTILINEAR] * n
        events = sim.simulate_n_pulses(n, bits, bases, bases)

        for i, event in enumerate(events):
            if event.detected:
                assert event.measured_bit == bits[i], (
                    f"Pulse {i}: expected {bits[i]}, got {event.measured_bit}"
                )

    def test_reset_clears_detector(self):
        sim = PhysicalLayerSimulator(seed=42)
        sim.simulate_pulse(0, Basis.RECTILINEAR, Basis.RECTILINEAR)
        sim.reset()
        # Should be able to detect immediately after reset
        event = sim.simulate_pulse(0, Basis.RECTILINEAR, Basis.RECTILINEAR,
                                   pulse_index=0)
        assert isinstance(event, DetectionEvent)

    def test_configurable_parameters(self):
        custom = ChannelParameters(
            source_intensity_mu=0.5,
            fiber_length_km=5.0,
            detector_efficiency=0.15,
        )
        sim = PhysicalLayerSimulator(custom, seed=42)
        assert sim.params.source_intensity_mu == 0.5
        assert sim.params.fiber_length_km == 5.0
        assert sim.params.detector_efficiency == 0.15
