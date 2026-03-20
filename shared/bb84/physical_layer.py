"""BB84 physical layer simulation.

Models the optical chain for quantum key distribution:
  - Mode-locked laser source with Poissonian photon statistics
  - Fiber-optic quantum channel with attenuation
  - Polarization encoding via nonlinear crystals (BB84 bases)
  - Single-photon detectors with realistic noise characteristics

All parameters are configurable via the ChannelParameters dataclass.
"""
import math
import numpy as np
from dataclasses import dataclass, field
from enum import Enum


class Polarization(Enum):
    """Polarization states used in BB84 encoding."""
    H = 0   # Horizontal (bit 0, rectilinear basis)
    V = 1   # Vertical   (bit 1, rectilinear basis)
    D = 2   # Diagonal +45° (bit 0, diagonal basis)
    A = 3   # Anti-diagonal -45° (bit 1, diagonal basis)


class Basis(Enum):
    """Measurement bases for BB84."""
    RECTILINEAR = 0  # H/V basis (+ basis)
    DIAGONAL = 1     # D/A basis (x basis)


@dataclass
class ChannelParameters:
    """Physical parameters for the quantum channel simulation.

    Defaults model a realistic tabletop QKD system with short fiber.
    """
    # Source
    source_intensity_mu: float = 0.1     # Mean photon number per pulse (Poisson)

    # Channel
    fiber_length_km: float = 1.0         # Fiber length
    attenuation_db_per_km: float = 0.2   # Fiber loss at 1550nm

    # Detector
    detector_efficiency: float = 0.10    # Single-photon detector efficiency
    dark_count_rate: float = 1e-5        # Dark count probability per gate window
    dead_time_ns: float = 50.0           # Detector recovery time
    jitter_ns: float = 0.5              # Timing jitter (std dev)
    afterpulse_probability: float = 0.01 # Afterpulse probability after a click

    # Alignment
    misalignment_angle_deg: float = 1.0  # Optical axis misalignment


@dataclass
class DetectionEvent:
    """Result of a single photon detection attempt."""
    pulse_index: int
    detected: bool
    measured_bit: int | None   # None if not detected
    basis: Basis
    is_dark_count: bool = False
    is_afterpulse: bool = False


# Mapping from (bit, basis) to polarization state
_BIT_BASIS_TO_POLARIZATION = {
    (0, Basis.RECTILINEAR): Polarization.H,
    (1, Basis.RECTILINEAR): Polarization.V,
    (0, Basis.DIAGONAL): Polarization.D,
    (1, Basis.DIAGONAL): Polarization.A,
}

# Mapping from polarization to (bit, basis)
_POLARIZATION_TO_BIT_BASIS = {v: k for k, v in _BIT_BASIS_TO_POLARIZATION.items()}


class PhotonSource:
    """Mode-locked laser attenuated to weak coherent pulses.

    Emits photon pulses following Poisson statistics with mean photon
    number mu (typically ~0.1 to minimize multi-photon events that
    enable photon-number splitting attacks).
    """

    def __init__(self, params: ChannelParameters, rng: np.random.Generator | None = None):
        self.mu = params.source_intensity_mu
        self._rng = rng or np.random.default_rng()

    def emit_pulse(self, bit: int, basis: Basis) -> tuple[int, Polarization]:
        """Emit a pulse with the given bit encoded in the given basis.

        Returns (n_photons, polarization) where n_photons is drawn from
        Poisson(mu).
        """
        n_photons = self._rng.poisson(self.mu)
        polarization = _BIT_BASIS_TO_POLARIZATION[(bit, basis)]
        return n_photons, polarization


class QuantumChannel:
    """Fiber-optic quantum channel with loss.

    Each photon independently survives with probability determined by
    the fiber attenuation and length.
    """

    def __init__(self, params: ChannelParameters, rng: np.random.Generator | None = None):
        total_loss_db = params.attenuation_db_per_km * params.fiber_length_km
        self.transmission_prob = 10 ** (-total_loss_db / 10)
        self._rng = rng or np.random.default_rng()

    def transmit(self, n_photons: int) -> int:
        """Transmit photons through the fiber. Returns number surviving."""
        if n_photons == 0:
            return 0
        surviving = self._rng.binomial(n_photons, self.transmission_prob)
        return int(surviving)


class SinglePhotonDetector:
    """Single-photon detector (e.g., InGaAs APD in gated mode).

    Models:
    - Detection efficiency
    - Dark counts (thermal noise)
    - Afterpulsing (correlated noise after a detection)
    - Dead time (detector recovery period)
    - Basis mismatch (random outcome when measuring in wrong basis)
    - Optical misalignment
    """

    def __init__(self, params: ChannelParameters, rng: np.random.Generator | None = None):
        self.params = params
        self._rng = rng or np.random.default_rng()
        self._last_detection_index: int | None = None
        # Convert dead time to pulse indices (assume ~1 GHz repetition rate)
        self._dead_time_pulses = max(1, int(params.dead_time_ns))
        # Misalignment error probability
        misalignment_rad = math.radians(params.misalignment_angle_deg)
        self._misalignment_error_prob = math.sin(misalignment_rad) ** 2

    def detect(self, n_photons: int, sent_polarization: Polarization,
               measurement_basis: Basis, pulse_index: int) -> DetectionEvent:
        """Attempt to detect photons and measure the polarization state."""

        # Dead time check: if detector hasn't recovered, no detection
        if self._last_detection_index is not None:
            if pulse_index - self._last_detection_index < self._dead_time_pulses:
                return DetectionEvent(
                    pulse_index=pulse_index,
                    detected=False,
                    measured_bit=None,
                    basis=measurement_basis,
                )

        # Afterpulse check
        is_afterpulse = False
        if self._last_detection_index is not None:
            gap = pulse_index - self._last_detection_index
            if gap < self._dead_time_pulses * 3:
                if self._rng.random() < self.params.afterpulse_probability:
                    is_afterpulse = True

        # Dark count check (independent of photon arrival)
        is_dark_count = self._rng.random() < self.params.dark_count_rate

        # Photon detection: each surviving photon has detector_efficiency
        # chance of triggering
        photon_detected = False
        if n_photons > 0:
            photon_detected = self._rng.binomial(
                n_photons, self.params.detector_efficiency
            ) > 0

        # Overall click: dark count OR photon detection OR afterpulse
        clicked = photon_detected or is_dark_count or is_afterpulse

        if not clicked:
            return DetectionEvent(
                pulse_index=pulse_index,
                detected=False,
                measured_bit=None,
                basis=measurement_basis,
            )

        # Record detection for dead time and afterpulse tracking
        self._last_detection_index = pulse_index

        # Determine measured bit
        sent_bit, sent_basis = _POLARIZATION_TO_BIT_BASIS[sent_polarization]

        if is_dark_count and not photon_detected:
            # Dark count: completely random outcome
            measured_bit = int(self._rng.integers(0, 2))
        elif measurement_basis == sent_basis:
            # Correct basis: deterministic (with small misalignment error)
            if self._rng.random() < self._misalignment_error_prob:
                measured_bit = 1 - sent_bit  # Misalignment error
            else:
                measured_bit = sent_bit
        else:
            # Wrong basis: 50/50 random outcome (quantum mechanics)
            measured_bit = int(self._rng.integers(0, 2))

        return DetectionEvent(
            pulse_index=pulse_index,
            detected=True,
            measured_bit=measured_bit,
            basis=measurement_basis,
            is_dark_count=is_dark_count and not photon_detected,
            is_afterpulse=is_afterpulse and not photon_detected and not is_dark_count,
        )

    def reset(self):
        """Reset detector state (clear dead time history)."""
        self._last_detection_index = None


class PhysicalLayerSimulator:
    """Facade for the complete optical chain simulation.

    Usage:
        sim = PhysicalLayerSimulator()
        event = sim.simulate_pulse(bit=1, alice_basis=Basis.RECTILINEAR,
                                    bob_basis=Basis.RECTILINEAR)
        if event.detected:
            print(f"Bob measured: {event.measured_bit}")
    """

    def __init__(self, params: ChannelParameters | None = None,
                 seed: int | None = None):
        self.params = params or ChannelParameters()
        self._rng = np.random.default_rng(seed)
        self.source = PhotonSource(self.params, self._rng)
        self.channel = QuantumChannel(self.params, self._rng)
        self.detector = SinglePhotonDetector(self.params, self._rng)

    def simulate_pulse(self, bit: int, alice_basis: Basis,
                       bob_basis: Basis, pulse_index: int = 0) -> DetectionEvent:
        """Simulate a single photon pulse through the full optical chain."""
        n_photons, polarization = self.source.emit_pulse(bit, alice_basis)
        n_surviving = self.channel.transmit(n_photons)
        event = self.detector.detect(n_surviving, polarization, bob_basis, pulse_index)
        return event

    def simulate_n_pulses(self, n: int,
                          alice_bits: list[int],
                          alice_bases: list[Basis],
                          bob_bases: list[Basis]) -> list[DetectionEvent]:
        """Simulate n pulses through the optical chain.

        Args:
            n: Number of pulses
            alice_bits: Bit values Alice encodes (length n)
            alice_bases: Bases Alice uses for encoding (length n)
            bob_bases: Bases Bob uses for measurement (length n)

        Returns:
            List of DetectionEvents for each pulse
        """
        events = []
        for i in range(n):
            event = self.simulate_pulse(
                alice_bits[i], alice_bases[i], bob_bases[i], pulse_index=i
            )
            events.append(event)
        return events

    def reset(self):
        """Reset detector state for a new simulation run."""
        self.detector.reset()
