"""BB84 quantum key distribution protocol engine.

Implements the full BB84 protocol:
  1. Alice generates random bits and random bases, sends encoded photons
  2. Bob measures with random bases
  3. Sifting: keep only bits where bases match
  4. QBER estimation: sacrifice a sample to estimate error rate
  5. Error correction: Cascade protocol to reconcile remaining errors
  6. Privacy amplification: Toeplitz hashing to eliminate Eve's information

Includes an eavesdropper simulator for demonstrating intrusion detection.
"""
import time
from dataclasses import dataclass, field

import numpy as np

from shared.bb84.physical_layer import (
    Basis,
    ChannelParameters,
    DetectionEvent,
    PhysicalLayerSimulator,
)
from shared.bb84.utils import binary_entropy, toeplitz_hash


@dataclass
class BB84ProtocolConfig:
    """Configuration for a BB84 protocol round."""
    num_raw_bits: int = 4096             # Pulses per key generation round
    qber_sample_fraction: float = 0.1    # Fraction of sifted bits sacrificed for QBER
    qber_threshold: float = 0.11         # Abort threshold (11%)
    target_key_length_bits: int = 128    # Desired final key length
    channel_params: ChannelParameters = field(default_factory=ChannelParameters)


@dataclass
class SiftedKeyResult:
    """Result of the key sifting step."""
    alice_sifted_bits: list[int]
    bob_sifted_bits: list[int]
    matching_indices: list[int]
    raw_key_rate: float       # sifted_bits / total_pulses
    detection_rate: float     # detected_pulses / total_pulses


@dataclass
class QBEREstimate:
    """Result of QBER estimation."""
    qber: float
    sample_size: int
    errors_found: int
    is_secure: bool           # qber < threshold


@dataclass
class BB84RoundResult:
    """Complete result of one BB84 protocol round."""
    key: bytes | None          # None if aborted
    qber: float
    is_secure: bool
    raw_bits_generated: int
    sifted_bits: int
    final_key_bits: int
    detection_events: int
    dark_count_fraction: float
    multi_photon_fraction: float
    aborted: bool
    abort_reason: str | None
    duration_seconds: float


class EavesdropperSimulator:
    """Simulates Eve performing an intercept-resend attack.

    Eve intercepts photons, measures them in a random basis, and
    re-sends based on her measurement. When her basis doesn't match
    Alice's, she introduces ~25% error on those bits (50% of the time
    she picks the wrong basis, and when she does, Bob gets a random
    result 50% of the time).
    """

    def __init__(self, interception_rate: float = 1.0,
                 seed: int | None = None):
        """
        Args:
            interception_rate: Fraction of pulses Eve intercepts (0-1).
                1.0 = full intercept-resend attack.
            seed: Random seed for reproducibility.
        """
        self.interception_rate = interception_rate
        self._rng = np.random.default_rng(seed)

    def intercept_resend(self, bit: int, alice_basis: Basis
                         ) -> tuple[int, Basis]:
        """Eve intercepts and re-sends a photon.

        Returns (eve_measured_bit, eve_basis). If Eve's basis matches
        Alice's, she measures the correct bit. If not, she gets a
        random result and re-sends in her (wrong) basis.
        """
        # Eve picks a random basis
        eve_basis = Basis(int(self._rng.integers(0, 2)))

        if eve_basis == alice_basis:
            # Eve measures correctly
            eve_bit = bit
        else:
            # Wrong basis: 50/50 random outcome
            eve_bit = int(self._rng.integers(0, 2))

        return eve_bit, eve_basis


class BB84Protocol:
    """Full BB84 quantum key distribution protocol.

    Usage:
        protocol = BB84Protocol()
        result = protocol.run_round()
        if not result.aborted:
            key = result.key  # Use this key for encryption
        else:
            print(f"Aborted: {result.abort_reason}")

    With eavesdropper:
        eve = EavesdropperSimulator(interception_rate=1.0)
        result = protocol.run_round(eavesdropper=eve)
        # result.qber will be ~0.25, result.aborted will be True
    """

    def __init__(self, config: BB84ProtocolConfig | None = None,
                 seed: int | None = None):
        self.config = config or BB84ProtocolConfig()
        self._rng = np.random.default_rng(seed)

    def run_round(self, eavesdropper: EavesdropperSimulator | None = None
                  ) -> BB84RoundResult:
        """Execute one complete BB84 protocol round."""
        t_start = time.monotonic()
        n = self.config.num_raw_bits

        # Step 1: Alice generates random bits and bases
        alice_bits = [int(x) for x in self._rng.integers(0, 2, size=n)]
        alice_bases = [Basis(int(x)) for x in self._rng.integers(0, 2, size=n)]

        # Step 2: Bob generates random measurement bases
        bob_bases = [Basis(int(x)) for x in self._rng.integers(0, 2, size=n)]

        # Step 3: Simulate quantum channel (with optional eavesdropper)
        sim = PhysicalLayerSimulator(self.config.channel_params)

        if eavesdropper is not None:
            # Eve intercepts and re-sends
            eve_bits = []
            eve_bases = []
            for i in range(n):
                if self._rng.random() < eavesdropper.interception_rate:
                    eve_bit, eve_basis = eavesdropper.intercept_resend(
                        alice_bits[i], alice_bases[i]
                    )
                    eve_bits.append(eve_bit)
                    eve_bases.append(eve_basis)
                else:
                    # Not intercepted: pass through
                    eve_bits.append(alice_bits[i])
                    eve_bases.append(alice_bases[i])

            # Bob receives Eve's re-sent photons (encoded in Eve's basis)
            events = sim.simulate_n_pulses(n, eve_bits, eve_bases, bob_bases)
        else:
            events = sim.simulate_n_pulses(n, alice_bits, alice_bases, bob_bases)

        # Count detection statistics
        detected_count = sum(1 for e in events if e.detected)
        dark_count_total = sum(1 for e in events if e.is_dark_count)

        if detected_count == 0:
            return BB84RoundResult(
                key=None, qber=1.0, is_secure=False,
                raw_bits_generated=n, sifted_bits=0, final_key_bits=0,
                detection_events=0, dark_count_fraction=0.0,
                multi_photon_fraction=0.0,
                aborted=True, abort_reason="No photons detected",
                duration_seconds=time.monotonic() - t_start,
            )

        # Step 4: Sifting — keep only matching-basis detections
        sifted = self._sift_keys(alice_bits, alice_bases, bob_bases, events)

        if len(sifted.alice_sifted_bits) < 10:
            return BB84RoundResult(
                key=None, qber=1.0, is_secure=False,
                raw_bits_generated=n, sifted_bits=len(sifted.alice_sifted_bits),
                final_key_bits=0, detection_events=detected_count,
                dark_count_fraction=dark_count_total / max(detected_count, 1),
                multi_photon_fraction=0.0,
                aborted=True, abort_reason="Insufficient sifted bits",
                duration_seconds=time.monotonic() - t_start,
            )

        # Step 5: QBER estimation
        qber_est = self._estimate_qber(
            sifted.alice_sifted_bits, sifted.bob_sifted_bits,
            self.config.qber_sample_fraction
        )

        if not qber_est.is_secure:
            return BB84RoundResult(
                key=None, qber=qber_est.qber, is_secure=False,
                raw_bits_generated=n, sifted_bits=len(sifted.alice_sifted_bits),
                final_key_bits=0, detection_events=detected_count,
                dark_count_fraction=dark_count_total / max(detected_count, 1),
                multi_photon_fraction=0.0,
                aborted=True,
                abort_reason=f"QBER {qber_est.qber:.4f} exceeds threshold {self.config.qber_threshold}",
                duration_seconds=time.monotonic() - t_start,
            )

        # Step 6: Remove QBER sample bits, keep the rest
        sample_size = qber_est.sample_size
        alice_remaining = sifted.alice_sifted_bits[sample_size:]
        bob_remaining = sifted.bob_sifted_bits[sample_size:]

        if len(alice_remaining) < self.config.target_key_length_bits:
            # Not enough bits for the target key after sampling
            # Try error correction anyway
            pass

        # Step 7: Error correction (simplified Cascade)
        corrected_bits = self._error_correct_cascade(
            alice_remaining, bob_remaining, qber_est.qber
        )

        # Step 8: Privacy amplification
        key = self._privacy_amplify(
            corrected_bits, qber_est.qber, self.config.target_key_length_bits
        )

        if key is None:
            return BB84RoundResult(
                key=None, qber=qber_est.qber, is_secure=True,
                raw_bits_generated=n, sifted_bits=len(sifted.alice_sifted_bits),
                final_key_bits=0, detection_events=detected_count,
                dark_count_fraction=dark_count_total / max(detected_count, 1),
                multi_photon_fraction=0.0,
                aborted=True,
                abort_reason="Insufficient bits after privacy amplification",
                duration_seconds=time.monotonic() - t_start,
            )

        return BB84RoundResult(
            key=key,
            qber=qber_est.qber,
            is_secure=True,
            raw_bits_generated=n,
            sifted_bits=len(sifted.alice_sifted_bits),
            final_key_bits=len(key) * 8,
            detection_events=detected_count,
            dark_count_fraction=dark_count_total / max(detected_count, 1),
            multi_photon_fraction=0.0,
            aborted=False,
            abort_reason=None,
            duration_seconds=time.monotonic() - t_start,
        )

    def _sift_keys(self, alice_bits: list[int], alice_bases: list[Basis],
                   bob_bases: list[Basis],
                   events: list[DetectionEvent]) -> SiftedKeyResult:
        """Keep only bits where both bases match and Bob detected a photon."""
        alice_sifted = []
        bob_sifted = []
        matching_indices = []

        for i, event in enumerate(events):
            if event.detected and alice_bases[i] == bob_bases[i]:
                alice_sifted.append(alice_bits[i])
                bob_sifted.append(event.measured_bit)
                matching_indices.append(i)

        total = len(events)
        detected = sum(1 for e in events if e.detected)

        return SiftedKeyResult(
            alice_sifted_bits=alice_sifted,
            bob_sifted_bits=bob_sifted,
            matching_indices=matching_indices,
            raw_key_rate=len(alice_sifted) / total if total > 0 else 0.0,
            detection_rate=detected / total if total > 0 else 0.0,
        )

    def _estimate_qber(self, alice_sifted: list[int], bob_sifted: list[int],
                       sample_fraction: float) -> QBEREstimate:
        """Estimate QBER by sacrificing a fraction of sifted bits."""
        sample_size = max(1, int(len(alice_sifted) * sample_fraction))
        sample_size = min(sample_size, len(alice_sifted))

        errors = sum(
            1 for i in range(sample_size)
            if alice_sifted[i] != bob_sifted[i]
        )
        qber = errors / sample_size if sample_size > 0 else 0.0

        return QBEREstimate(
            qber=qber,
            sample_size=sample_size,
            errors_found=errors,
            is_secure=qber < self.config.qber_threshold,
        )

    def _error_correct_cascade(self, alice_bits: list[int],
                                bob_bits: list[int],
                                qber: float) -> list[int]:
        """Simplified Cascade error correction.

        Cascade works by:
        1. Divide bits into blocks of size ~0.73/QBER
        2. Compare parity of each block
        3. Binary search for errors in mismatched blocks
        4. Repeat with doubled block size for 4 passes

        In this simulation, Alice and Bob share parity information over
        the authenticated classical channel. We simulate this directly
        since both bit strings are available.
        """
        if len(alice_bits) == 0:
            return []

        # Work on Bob's copy — correct it to match Alice
        corrected = list(bob_bits)
        n = len(corrected)

        if qber <= 0:
            return corrected

        # Initial block size from Cascade literature
        initial_block_size = max(2, int(0.73 / qber))
        num_passes = 4

        for pass_num in range(num_passes):
            block_size = min(initial_block_size * (2 ** pass_num), n)

            # Shuffle indices for this pass (except first pass)
            if pass_num == 0:
                indices = list(range(n))
            else:
                indices = list(self._rng.permutation(n))

            # Process blocks
            for block_start in range(0, n, block_size):
                block_end = min(block_start + block_size, n)
                block_indices = indices[block_start:block_end]

                # Compare parity
                alice_parity = sum(alice_bits[idx] for idx in block_indices) % 2
                bob_parity = sum(corrected[idx] for idx in block_indices) % 2

                if alice_parity != bob_parity:
                    # Binary search for the error
                    self._binary_search_correct(
                        alice_bits, corrected, block_indices
                    )

        return corrected

    def _binary_search_correct(self, alice_bits: list[int],
                                corrected: list[int],
                                block_indices: list[int]) -> None:
        """Binary search within a block to find and correct one error."""
        if len(block_indices) <= 1:
            if len(block_indices) == 1:
                idx = block_indices[0]
                corrected[idx] = alice_bits[idx]  # Correct the bit
            return

        mid = len(block_indices) // 2
        left_indices = block_indices[:mid]
        right_indices = block_indices[mid:]

        # Check left half parity
        alice_left_parity = sum(alice_bits[idx] for idx in left_indices) % 2
        bob_left_parity = sum(corrected[idx] for idx in left_indices) % 2

        if alice_left_parity != bob_left_parity:
            self._binary_search_correct(alice_bits, corrected, left_indices)
        else:
            self._binary_search_correct(alice_bits, corrected, right_indices)

    def _privacy_amplify(self, corrected_bits: list[int], qber: float,
                         target_length: int) -> bytes | None:
        """Apply privacy amplification via Toeplitz hashing.

        The secure key length is bounded by:
            n * (1 - 2*h(QBER)) - security_parameter

        where h() is the binary entropy function. If QBER is too high,
        the remaining secure bits may be fewer than the target length.
        """
        n = len(corrected_bits)
        if n == 0:
            return None

        # Secure fraction: 1 - 2*h(QBER) accounts for Eve's information
        # from both the quantum channel and error correction
        h_qber = binary_entropy(qber) if qber > 0 else 0.0
        secure_fraction = max(0.0, 1.0 - 2 * h_qber)

        # Security parameter: extra bits discarded for composable security
        security_parameter = 64

        max_secure_bits = int(n * secure_fraction) - security_parameter

        if max_secure_bits < target_length:
            # Use whatever we can get, or fail
            if max_secure_bits <= 0:
                return None
            output_length = max_secure_bits
        else:
            output_length = target_length

        # Apply Toeplitz hash
        return toeplitz_hash(corrected_bits, output_length)
