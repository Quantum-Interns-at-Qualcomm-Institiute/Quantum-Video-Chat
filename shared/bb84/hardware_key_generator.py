"""Hardware-backed key generator with simulation fallback.

Reads key material from real QKD hardware via the bridge interface.
When hardware is not connected, falls back to the BB84 simulation
for seamless development and demonstration.
"""
from shared.bb84.hardware_bridge import AbstractHardwareBridge
from shared.encryption import AbstractKeyGenerator, BB84KeyGenerator


class HardwareKeyGenerator(AbstractKeyGenerator):
    """Key generator that reads from real QKD hardware.

    Falls back to BB84 simulation when hardware is unavailable.

    Args:
        bridge: Hardware bridge implementation (e.g., MATLABBridge).
        fallback_config: BB84ProtocolConfig for simulation fallback.
    """

    def __init__(self, bridge: AbstractHardwareBridge | None = None,
                 fallback_config=None):
        self._bridge = bridge
        self._fallback = BB84KeyGenerator(protocol_config=fallback_config)
        self.key: bytes = b''
        self._using_hardware = False

    @property
    def is_hardware_connected(self) -> bool:
        """Check if real hardware is connected."""
        return self._bridge is not None and self._bridge.is_connected()

    @property
    def using_hardware(self) -> bool:
        """Whether the last key was generated from real hardware."""
        return self._using_hardware

    def set_bridge(self, bridge: AbstractHardwareBridge):
        """Connect a hardware bridge at runtime."""
        self._bridge = bridge

    def generate_key(self, key_length=0, **kwargs):
        """Generate a key from hardware if available, else simulate."""
        num_bytes = (key_length + 7) // 8 if key_length else 16

        if self.is_hardware_connected:
            try:
                self.key = self._bridge.get_raw_key_material(num_bytes)
                self._using_hardware = True
                return
            except OSError:
                pass  # Fall through to simulation

        # Fallback to BB84 simulation
        self._using_hardware = False
        self._fallback.generate_key(key_length=key_length)
        self.key = self._fallback.get_key()

    def get_key(self) -> bytes:
        return self.key

    @property
    def last_round_result(self):
        """Access simulation metrics (None when using hardware)."""
        if self._using_hardware:
            return None
        return self._fallback.last_round_result

    @property
    def hardware_qber(self) -> float | None:
        """Read QBER from hardware sensors (None if not connected)."""
        if self.is_hardware_connected:
            try:
                return self._bridge.get_qber_estimate()
            except OSError:
                return None
        return None
