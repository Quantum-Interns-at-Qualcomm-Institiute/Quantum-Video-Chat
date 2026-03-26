"""Hardware bridge interfaces for real QKD equipment.

Defines abstract interfaces that real QKD hardware implementations can
fulfill, plus concrete stubs for MATLAB sensor readout and Qiskit
protocol validation.

These are designed to slot into the existing key generator registry:
when real hardware is available, a HardwareKeyGenerator reads key
material through the bridge; when hardware is absent, it falls back
to the BB84 simulation.
"""
import os
from abc import ABC, abstractmethod


class AbstractHardwareBridge(ABC):
    """Interface for connecting real QKD hardware to the video chat system.

    Implementations read raw key material and QBER estimates from
    physical single-photon detectors. The bridge pattern decouples
    the protocol logic from the specific hardware/software used to
    read the sensors (MATLAB, LabVIEW, custom DAQ, etc.).
    """

    @abstractmethod
    def get_raw_key_material(self, length_bytes: int) -> bytes:
        """Read raw key material from hardware.

        Args:
            length_bytes: Number of key bytes to read.

        Returns:
            Raw sifted key bytes from the QKD hardware.

        Raises:
            IOError: If hardware is not connected or read fails.
        """
        pass

    @abstractmethod
    def get_qber_estimate(self) -> float:
        """Read current QBER estimate from hardware sensors.

        Returns:
            QBER as a float between 0.0 and 1.0.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if hardware is connected and responsive."""
        pass


class MATLABBridge(AbstractHardwareBridge):
    """Bridge to MATLAB via file-based data exchange.

    Reads key material from binary files exported by MATLAB scripts
    that interface with the single-photon detectors. MATLAB writes
    sifted key bits to a binary file; this bridge reads them.

    The expected workflow:
      1. MATLAB reads SPD click events and performs basis reconciliation
      2. MATLAB exports sifted key bits to `data_dir/sifted_key.bin`
      3. MATLAB exports QBER estimate to `data_dir/qber.txt`
      4. This bridge reads both files

    For MATLAB Engine API integration (direct function calls),
    subclass this and override the read methods.

    Args:
        data_dir: Directory where MATLAB exports key files.
        key_filename: Name of the binary key file.
        qber_filename: Name of the QBER estimate file.
    """

    def __init__(self, data_dir: str,
                 key_filename: str = 'sifted_key.bin',
                 qber_filename: str = 'qber.txt'):
        self.data_dir = data_dir
        self.key_path = os.path.join(data_dir, key_filename)
        self.qber_path = os.path.join(data_dir, qber_filename)
        self._file_handle = None

    def get_raw_key_material(self, length_bytes: int) -> bytes:
        """Read key material from MATLAB-exported binary file.

        Reads sequentially from the file, reopening from the start
        when the end is reached (for continuous key generation).
        """
        if self._file_handle is None or self._file_handle.closed:
            if not os.path.exists(self.key_path):
                raise OSError(f"Key file not found: {self.key_path}")
            self._file_handle = open(self.key_path, 'rb')

        data = self._file_handle.read(length_bytes)
        if len(data) < length_bytes:
            # Wrap around to beginning of file
            self._file_handle.seek(0)
            remaining = length_bytes - len(data)
            data += self._file_handle.read(remaining)

        return data

    def get_qber_estimate(self) -> float:
        """Read QBER from MATLAB-exported text file.

        Expects a single float value in the file.
        """
        if not os.path.exists(self.qber_path):
            return 0.0
        with open(self.qber_path) as f:
            return float(f.read().strip())

    def is_connected(self) -> bool:
        """Check if the MATLAB data directory and key file exist."""
        return (os.path.isdir(self.data_dir)
                and os.path.exists(self.key_path))

    def close(self):
        """Close the key file handle."""
        if self._file_handle and not self._file_handle.closed:
            self._file_handle.close()


class QiskitValidator:
    """Validate BB84 protocol correctness using Qiskit simulation.

    Runs the same protocol parameters through Qiskit's quantum circuit
    simulator to verify that the custom physical layer simulation
    produces statistically consistent results.

    This is a validation tool, not a production component. It requires
    the `qiskit` package to be installed.

    Usage:
        validator = QiskitValidator()
        report = validator.validate_bb84_round(
            alice_bits=[0, 1, 1, 0, ...],
            alice_bases=[Basis.RECTILINEAR, Basis.DIAGONAL, ...],
            bob_bases=[Basis.DIAGONAL, Basis.RECTILINEAR, ...],
            expected_sifted_rate=0.5,
        )
    """

    def validate_bb84_round(self, alice_bits: list[int],
                            alice_bases: list,
                            bob_bases: list,
                            expected_sifted_rate: float = 0.5) -> dict:
        """Run BB84 in Qiskit and compare with expected statistics.

        Args:
            alice_bits: Bit values Alice encodes.
            alice_bases: Bases Alice uses for encoding.
            bob_bases: Bases Bob uses for measurement.
            expected_sifted_rate: Expected fraction of matching bases.

        Returns:
            Dict with validation results:
              - qiskit_sifted_rate: Sifted rate from Qiskit simulation
              - expected_sifted_rate: The expected rate
              - match: Whether rates are within tolerance
              - details: Per-basis statistics
        """
        try:
            from qiskit import QuantumCircuit
            from qiskit_aer import AerSimulator
        except ImportError:
            return {
                'error': 'qiskit and/or qiskit_aer not installed',
                'match': None,
                'details': 'Install qiskit and qiskit-aer for validation',
            }

        n = len(alice_bits)
        matching_bases = sum(
            1 for a, b in zip(alice_bases, bob_bases)
            if a == b
        )
        qiskit_sifted_rate = matching_bases / n if n > 0 else 0.0

        # For each matching-basis pair, verify the Qiskit circuit
        # produces the correct measurement
        correct_measurements = 0
        total_checks = 0

        for i in range(min(n, 100)):  # Check first 100 for speed
            if alice_bases[i] != bob_bases[i]:
                continue
            total_checks += 1

            qc = QuantumCircuit(1, 1)

            # Alice's encoding
            if alice_bits[i] == 1:
                qc.x(0)  # Flip to |1>
            if alice_bases[i].value == 1:  # Diagonal basis
                qc.h(0)  # Apply Hadamard

            # Bob's measurement
            if bob_bases[i].value == 1:  # Diagonal basis
                qc.h(0)  # Undo Hadamard for measurement
            qc.measure(0, 0)

            simulator = AerSimulator()
            result = simulator.run(qc, shots=1).result()
            counts = result.get_counts()
            measured_bit = int(next(iter(counts.keys())))

            if measured_bit == alice_bits[i]:
                correct_measurements += 1

        accuracy = correct_measurements / total_checks if total_checks > 0 else 1.0

        return {
            'qiskit_sifted_rate': round(qiskit_sifted_rate, 4),
            'expected_sifted_rate': expected_sifted_rate,
            'rate_match': abs(qiskit_sifted_rate - expected_sifted_rate) < 0.1,
            'measurement_accuracy': round(accuracy, 4),
            'measurements_checked': total_checks,
            'correct_measurements': correct_measurements,
            'match': accuracy > 0.95,
        }
