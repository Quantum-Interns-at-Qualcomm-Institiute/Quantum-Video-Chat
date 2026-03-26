"""Encryption schemes, key generators, and their registries."""

import os
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from Crypto.Cipher import AES

# region --- Encryption Schemes ---

class AbstractEncryptionScheme(ABC):
    """Base class for encryption scheme implementations."""

    @abstractmethod
    def encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypt the data using the provided key."""

    @abstractmethod
    def decrypt(self, data: bytes, key: bytes) -> bytes:
        """Decrypt the data using the provided key."""

    @abstractmethod
    def get_name(self) -> str:
        """Returns the Encryption Scheme's name."""


class XOREncryption(AbstractEncryptionScheme):
    """Simple XOR-based encryption (insecure, for development only)."""

    def __init__(self):
        """Initialize XOR encryption scheme."""
        self.name = "XOR"

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypt data by XORing with the key."""
        return bytes(a ^ b for a, b in zip(data, key * (len(data) // len(key) + 1), strict=False))

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        """Decrypt data by XORing with the key."""
        return self.encrypt(data, key)

    def get_name(self):
        """Return the scheme name."""
        return self.name


class DebugEncryption(AbstractEncryptionScheme):
    """No-op encryption for debugging (insecure)."""

    def __init__(self):
        """Initialize debug encryption scheme."""
        self.name = "Debug"

    def encrypt(self, data: bytes, _key: bytes) -> bytes:
        """Return data unchanged."""
        return data

    def decrypt(self, data: bytes, _key: bytes) -> bytes:
        """Return data unchanged."""
        return data

    def get_name(self):
        """Return the scheme name."""
        return self.name


class AESEncryption(AbstractEncryptionScheme):
    """AES-GCM authenticated encryption.

    Ciphertext format: nonce (12 bytes) || tag (16 bytes) || ciphertext
    """

    NONCE_SIZE = 12
    TAG_SIZE = 16

    def __init__(self, bits=128):
        """Initialize AES encryption with the given key size."""
        self.bits = bits
        self.name = f"AES-{bits}"

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypt data using AES-GCM."""
        nonce = os.urandom(self.NONCE_SIZE)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return nonce + tag + ciphertext

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        """Decrypt data using AES-GCM."""
        nonce = data[:self.NONCE_SIZE]
        tag = data[self.NONCE_SIZE:self.NONCE_SIZE + self.TAG_SIZE]
        ciphertext = data[self.NONCE_SIZE + self.TAG_SIZE:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)

    def get_name(self):
        """Return the scheme name."""
        return self.name

# endregion


# region --- Encryption Registry ---

_ENCRYPT_REGISTRY: dict[str, type[AbstractEncryptionScheme]] = {}


def register_encrypt_scheme(name: str, cls: type[AbstractEncryptionScheme]) -> None:
    """Register an encryption scheme class under the given name."""
    _ENCRYPT_REGISTRY[name] = cls


def create_encrypt_scheme(name: str) -> AbstractEncryptionScheme:
    """Create an encryption scheme by registered name."""
    if name not in _ENCRYPT_REGISTRY:
        msg = f"Invalid encryption scheme type: {name}"
        raise ValueError(msg)
    return _ENCRYPT_REGISTRY[name]()


# Built-in schemes
register_encrypt_scheme("AES", AESEncryption)

# XOR and DEBUG are insecure and only available when QVC_DEVELOPMENT=true
if os.environ.get("QVC_DEVELOPMENT", "").lower() in ("true", "1", "yes"):
    register_encrypt_scheme("XOR", XOREncryption)
    register_encrypt_scheme("DEBUG", DebugEncryption)


# Deprecated: enum + factory kept for backward compatibility.
class EncryptSchemes(Enum):
    """Deprecated enum of encryption scheme types."""

    ABSTRACT = AbstractEncryptionScheme
    AES = AESEncryption
    DEBUG = DebugEncryption
    XOR = XOREncryption


class EncryptFactory:
    """Deprecated: use create_encrypt_scheme(name) instead."""

    def create_encrypt_scheme(self, scheme_type) -> AbstractEncryptionScheme:
        """Create an encryption scheme from an EncryptSchemes enum value."""
        if isinstance(scheme_type, EncryptSchemes):
            return scheme_type.value()
        msg = f"Invalid encryption scheme type: {scheme_type}"
        raise TypeError(msg)

    def __enter__(self):
        """Return self as context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up context manager resources."""

# endregion


# region --- Key Generators ---

class AbstractKeyGenerator(ABC):
    """Base class for key generator implementations."""

    @abstractmethod
    def generate_key(self, *args, **kwargs) -> None:
        """Generate a key, either randomly or preset."""

    @abstractmethod
    def get_key(self) -> bytes:
        """Return the generated key as bytes."""


class DebugKeyGenerator(AbstractKeyGenerator):
    """Key generator for testing with deterministic keys."""

    def __init__(self):
        """Initialize with empty key."""
        self.key: bytes = b""
        self.key_length = 0

    def specified_keylength(self, length):
        """Generate a deterministic key of the given length."""
        self.key_length = length
        self.key = bytes([i % 2 for i in range(self.key_length)])

    def specified_key(self, key):
        """Set a specific key value."""
        if isinstance(key, bytes):
            self.key = key
        elif isinstance(key, str):
            self.key = key.encode("utf-8")
        else:
            msg = "Error, only bytes or string allowed"
            raise TypeError(msg)
        self.key_length = len(self.key)

    def generate_key(self, key=None, key_length=0):
        """Generate a key from explicit value or length."""
        if key is not None:
            self.specified_key(key)
        elif key_length != 0:
            self.specified_keylength(key_length)
        else:
            msg = "Invalid parameters"
            raise ValueError(msg)

    def get_key(self) -> bytes:
        """Return the current key."""
        return self.key


class RandomKeyGenerator(AbstractKeyGenerator):
    """Key generator using OS random bytes."""

    def __init__(self, key_length=0):
        """Initialize with optional default key length."""
        self.key_length = key_length
        self.key: bytes = b""

    def generate_key(self, key_length=0):
        """Generate a random key of the given bit length."""
        if key_length:
            self.key_length = key_length
        elif self.key_length < 1:
            msg = "Error, please make key length nonzero"
            raise ValueError(msg)
        num_bytes = (self.key_length + 7) // 8
        self.key = os.urandom(num_bytes)

    def get_key(self) -> bytes:
        """Return the current key."""
        return self.key


class FileKeyGenerator(AbstractKeyGenerator):
    """Key generator that reads key material from a binary file."""

    def __init__(self, file_name=None, key_length=0):
        """Initialize with key file path and optional key length."""
        if file_name is None:
            # Default: key.bin at the project root (parent of shared/)
            file_name = str(Path(__file__).resolve().parent.parent / "key.bin")
        self.key_length = key_length
        self.key: bytes = b""
        self.file_name = file_name
        self._file = None

    def close(self):
        """Close the key file if open."""
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self):
        """Return self as context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the key file on context exit."""
        self.close()

    def __del__(self):
        """Close the key file on garbage collection."""
        self.close()

    def generate_key(self, key_length=0):
        """Read key material from the file."""
        if key_length:
            self.key_length = key_length
        elif self.key_length < 1:
            msg = "Error, please make key length nonzero"
            raise ValueError(msg)
        num_bytes = (self.key_length + 7) // 8
        f = self._open()
        data = f.read(num_bytes)
        if len(data) < num_bytes:
            f.seek(0)
            data = f.read(num_bytes)
            if len(data) < num_bytes:
                msg = f"Key file too small: need {num_bytes} bytes, got {len(data)}"
                raise RuntimeError(msg)
        self.key = data

    def get_key(self) -> bytes:
        """Return the current key."""
        return self.key

    def _open(self):
        if self._file is None:
            self._file = Path(self.file_name).open("rb")  # noqa: SIM115 -- lazy-open pattern; closed by close()/context manager
        return self._file


class BB84KeyGenerator(AbstractKeyGenerator):
    """Key generator using simulated BB84 quantum key distribution.

    Runs a full BB84 protocol round (physical layer simulation, sifting,
    QBER estimation, error correction, privacy amplification) to produce
    each key. Reports metrics via an optional callback.
    """

    def __init__(self, protocol_config=None):
        """Initialize with optional BB84 protocol configuration."""
        from shared.bb84.protocol import BB84Protocol, BB84ProtocolConfig  # noqa: PLC0415
        self._config = protocol_config or BB84ProtocolConfig()
        self._protocol = BB84Protocol(self._config)
        self.key: bytes = b""
        self._last_round_result = None
        self._eavesdropper = None
        self._metrics_callback = None

    def set_eavesdropper(self, eavesdropper):
        """Enable eavesdropper simulation for demos."""
        self._eavesdropper = eavesdropper

    def clear_eavesdropper(self):
        """Disable eavesdropper simulation."""
        self._eavesdropper = None

    def set_metrics_callback(self, callback):
        """Register callback(BB84RoundResult) for QBER monitoring."""
        self._metrics_callback = callback

    def generate_key(self, key_length=0, **_kwargs):
        """Run a BB84 protocol round to generate a new key."""
        if key_length:
            self._config.target_key_length_bits = key_length

        result = self._protocol.run_round(eavesdropper=self._eavesdropper)
        self._last_round_result = result

        if self._metrics_callback:
            self._metrics_callback(result)

        if result.aborted or result.key is None:
            # Key generation failed — keep old key
            return

        self.key = result.key

    def get_key(self) -> bytes:
        """Return the current key."""
        return self.key

    @property
    def last_round_result(self):
        """Access the most recent BB84RoundResult for metrics."""
        return self._last_round_result


# endregion


# region --- Key Generator Registry ---

_KEYGEN_REGISTRY: dict[str, type[AbstractKeyGenerator]] = {}


def register_key_generator(name: str, cls: type[AbstractKeyGenerator]) -> None:
    """Register a key generator class under the given name."""
    _KEYGEN_REGISTRY[name] = cls


def create_key_generator(name: str) -> AbstractKeyGenerator:
    """Create a key generator by registered name."""
    if name not in _KEYGEN_REGISTRY:
        msg = f"Invalid key generator type: {name}"
        raise ValueError(msg)
    return _KEYGEN_REGISTRY[name]()


# Built-in generators
register_key_generator("FILE", FileKeyGenerator)
register_key_generator("RANDOM", RandomKeyGenerator)
register_key_generator("DEBUG", DebugKeyGenerator)
register_key_generator("BB84", BB84KeyGenerator)


# Deprecated: enum + factory kept for backward compatibility.
class KeyGenerators(Enum):
    """Deprecated enum of key generator types."""

    ABSTRACT = AbstractKeyGenerator
    FILE = FileKeyGenerator
    RANDOM = RandomKeyGenerator
    DEBUG = DebugKeyGenerator
    BB84 = BB84KeyGenerator


class KeyGenFactory:
    """Deprecated: use create_key_generator(name) instead."""

    def create_key_generator(self, generator_type) -> AbstractKeyGenerator:
        """Create a key generator from a KeyGenerators enum value."""
        if isinstance(generator_type, KeyGenerators):
            return generator_type.value()
        msg = f"Invalid key generator type: {generator_type}"
        raise TypeError(msg)

    def __enter__(self):
        """Return self as context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up context manager resources."""

# endregion
