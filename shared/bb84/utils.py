"""Utility functions for BB84 protocol operations.

Provides binary entropy, Toeplitz hashing for privacy amplification,
and bit/byte conversion helpers.
"""
import math
import numpy as np


def binary_entropy(p: float) -> float:
    """Compute the binary entropy function h(p).

    h(p) = -p*log2(p) - (1-p)*log2(1-p)

    Returns 0 for p=0 or p=1 (by convention).
    """
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def bits_to_bytes(bits: list[int]) -> bytes:
    """Convert a list of bits (0/1 ints) to a bytes object.

    Pads with zeros on the right if len(bits) is not a multiple of 8.
    """
    # Pad to multiple of 8
    padded = bits + [0] * ((8 - len(bits) % 8) % 8)
    result = bytearray()
    for i in range(0, len(padded), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | padded[i + j]
        result.append(byte)
    return bytes(result)


def bytes_to_bits(data: bytes) -> list[int]:
    """Convert bytes to a list of bits (0/1 ints), MSB first."""
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def toeplitz_hash(bits: list[int], output_length: int,
                  seed: bytes | None = None) -> bytes:
    """Apply a random Toeplitz matrix hash for privacy amplification.

    A Toeplitz matrix is defined by its first row and first column,
    requiring only (n + m - 1) random bits for an m x n matrix.
    This provides 2-universal hashing suitable for privacy amplification.

    Args:
        bits: Input bit string to hash
        output_length: Desired output length in bits
        seed: Random seed for reproducibility (optional)

    Returns:
        Hashed output as bytes
    """
    n = len(bits)
    m = output_length

    if m <= 0 or n <= 0:
        return b''

    rng = np.random.default_rng(
        int.from_bytes(seed, 'big') if seed else None
    )

    # Generate random bits for Toeplitz matrix definition
    # First row (m bits) + first column minus first element (n-1 bits)
    random_bits = rng.integers(0, 2, size=n + m - 1)

    # Construct the Toeplitz matrix and multiply
    input_arr = np.array(bits, dtype=np.int8)
    output_bits = []

    for i in range(m):
        # Row i of Toeplitz matrix is random_bits[i:i+n]
        row = random_bits[i:i + n]
        bit = int(np.dot(row, input_arr)) % 2
        output_bits.append(bit)

    return bits_to_bytes(output_bits)
