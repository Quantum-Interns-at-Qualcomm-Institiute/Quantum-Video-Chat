import os
from abc import ABC, abstractmethod
from enum import Enum
from Crypto.Cipher import AES


# region --- Encryption Schemes ---

class AbstractEncryptionScheme(ABC):
    @abstractmethod
    def encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypt the data using the provided key."""
        pass

    @abstractmethod
    def decrypt(self, data: bytes, key: bytes) -> bytes:
        """Decrypt the data using the provided key."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Returns the Encryption Scheme's name."""
        pass


class XOREncryption(AbstractEncryptionScheme):
    def __init__(self):
        self.name = "XOR"

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(data, key * (len(data) // len(key) + 1)))

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        return self.encrypt(data, key)

    def get_name(self):
        return self.name


class DebugEncryption(AbstractEncryptionScheme):
    def __init__(self):
        self.name = "Debug"

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        return data

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        return data

    def get_name(self):
        return self.name


class AESEncryption(AbstractEncryptionScheme):
    """AES-GCM authenticated encryption.

    Ciphertext format: nonce (12 bytes) || tag (16 bytes) || ciphertext
    """

    NONCE_SIZE = 12
    TAG_SIZE = 16

    def __init__(self, bits=128):
        self.bits = bits
        self.name = f"AES-{bits}"

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        nonce = os.urandom(self.NONCE_SIZE)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return nonce + tag + ciphertext

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        nonce = data[:self.NONCE_SIZE]
        tag = data[self.NONCE_SIZE:self.NONCE_SIZE + self.TAG_SIZE]
        ciphertext = data[self.NONCE_SIZE + self.TAG_SIZE:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)

    def get_name(self):
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
        raise ValueError(f"Invalid encryption scheme type: {name}")
    return _ENCRYPT_REGISTRY[name]()


# Built-in schemes
register_encrypt_scheme('AES', AESEncryption)

# XOR and DEBUG are insecure and only available when QVC_DEVELOPMENT=true
if os.environ.get('QVC_DEVELOPMENT', '').lower() in ('true', '1', 'yes'):
    register_encrypt_scheme('XOR', XOREncryption)
    register_encrypt_scheme('DEBUG', DebugEncryption)


# Deprecated: enum + factory kept for backward compatibility.
class EncryptSchemes(Enum):
    ABSTRACT = AbstractEncryptionScheme
    AES = AESEncryption
    DEBUG = DebugEncryption
    XOR = XOREncryption


class EncryptFactory:
    """Deprecated: use create_encrypt_scheme(name) instead."""
    def create_encrypt_scheme(self, type) -> AbstractEncryptionScheme:
        if isinstance(type, EncryptSchemes):
            return type.value()
        raise ValueError(f"Invalid encryption scheme type: {type}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# endregion


# region --- Key Generators ---

class AbstractKeyGenerator(ABC):
    @abstractmethod
    def generate_key(self, *args, **kwargs) -> None:
        """Generate a key, either randomly or preset."""
        pass

    @abstractmethod
    def get_key(self) -> bytes:
        """Return the generated key as bytes."""
        pass


class DebugKeyGenerator(AbstractKeyGenerator):
    def __init__(self):
        self.key: bytes = b''
        self.key_length = 0

    def specified_keylength(self, length):
        self.key_length = length
        self.key = bytes([i % 2 for i in range(self.key_length)])

    def specified_key(self, key):
        if isinstance(key, bytes):
            self.key = key
        elif isinstance(key, str):
            self.key = key.encode('utf-8')
        else:
            raise ValueError("Error, only bytes or string allowed")
        self.key_length = len(self.key)

    def generate_key(self, key=None, key_length=0):
        if key is not None:
            self.specified_key(key)
        elif key_length != 0:
            self.specified_keylength(key_length)
        else:
            raise ValueError("Invalid parameters")

    def get_key(self) -> bytes:
        return self.key


class RandomKeyGenerator(AbstractKeyGenerator):
    def __init__(self, key_length=0):
        self.key_length = key_length
        self.key: bytes = b''

    def generate_key(self, key_length=0):
        if key_length:
            self.key_length = key_length
        elif self.key_length < 1:
            raise ValueError("Error, please make key length nonzero")
        num_bytes = (self.key_length + 7) // 8
        self.key = os.urandom(num_bytes)

    def get_key(self) -> bytes:
        return self.key


class FileKeyGenerator(AbstractKeyGenerator):
    def __init__(self, file_name=None, key_length=0):
        if file_name is None:
            # Default: key.bin at the project root (parent of shared/)
            _shared_dir = os.path.dirname(os.path.abspath(__file__))
            file_name = os.path.join(os.path.dirname(_shared_dir), "key.bin")
        self.key_length = key_length
        self.key: bytes = b''
        self.file_name = file_name
        self._file = None

    def _open(self):
        if self._file is None:
            self._file = open(self.file_name, "rb")
        return self._file

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def generate_key(self, key_length=0):
        if key_length:
            self.key_length = key_length
        elif self.key_length < 1:
            raise ValueError("Error, please make key length nonzero")
        num_bytes = (self.key_length + 7) // 8
        f = self._open()
        data = f.read(num_bytes)
        if len(data) < num_bytes:
            f.seek(0)
            data = f.read(num_bytes)
            if len(data) < num_bytes:
                raise RuntimeError(f"Key file too small: need {num_bytes} bytes, got {len(data)}")
        self.key = data

    def get_key(self) -> bytes:
        return self.key


class BB84KeyGenerator(AbstractKeyGenerator):
    """Key generator using simulated BB84 quantum key distribution.

    Runs a full BB84 protocol round (physical layer simulation, sifting,
    QBER estimation, error correction, privacy amplification) to produce
    each key. Reports metrics via an optional callback.
    """

    def __init__(self, protocol_config=None):
        from shared.bb84.protocol import BB84Protocol, BB84ProtocolConfig
        self._config = protocol_config or BB84ProtocolConfig()
        self._protocol = BB84Protocol(self._config)
        self.key: bytes = b''
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

    def generate_key(self, key_length=0, **kwargs):
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
        raise ValueError(f"Invalid key generator type: {name}")
    return _KEYGEN_REGISTRY[name]()


# Built-in generators
register_key_generator('FILE', FileKeyGenerator)
register_key_generator('RANDOM', RandomKeyGenerator)
register_key_generator('DEBUG', DebugKeyGenerator)
register_key_generator('BB84', BB84KeyGenerator)


# Deprecated: enum + factory kept for backward compatibility.
class KeyGenerators(Enum):
    ABSTRACT = AbstractKeyGenerator
    FILE = FileKeyGenerator
    RANDOM = RandomKeyGenerator
    DEBUG = DebugKeyGenerator
    BB84 = BB84KeyGenerator


class KeyGenFactory:
    """Deprecated: use create_key_generator(name) instead."""
    def create_key_generator(self, type) -> AbstractKeyGenerator:
        if isinstance(type, KeyGenerators):
            return type.value()
        raise ValueError(f"Invalid key generator type: {type}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# endregion
