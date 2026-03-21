import os
import string
from abc import ABC, abstractmethod
from enum import Enum
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


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
    def __init__(self, bits=128):
        self.bits = bits
        self.name = f"AES-{bits}"
        self.results = []

    def encrypt(self, data: bytes, key: bytes) -> bytes:
        cipher = AES.new(key, AES.MODE_CBC, iv=b'0' * 16)
        data = pad(data, AES.block_size)
        return cipher.encrypt(data)

    def decrypt(self, data: bytes, key: bytes) -> bytes:
        iv = b'0' * 16
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(data)
        return unpad(decrypted, AES.block_size)

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
        if type in EncryptSchemes:
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

    def speficied_keylength(self, length):
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
            self.speficied_keylength(key_length)
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
        self.key = self._open().read(num_bytes)

    def get_key(self) -> bytes:
        return self.key

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


# Deprecated: enum + factory kept for backward compatibility.
class KeyGenerators(Enum):
    ABSTRACT = AbstractKeyGenerator
    FILE = FileKeyGenerator
    RANDOM = RandomKeyGenerator
    DEBUG = DebugKeyGenerator


class KeyGenFactory:
    """Deprecated: use create_key_generator(name) instead."""
    def create_key_generator(self, type) -> AbstractKeyGenerator:
        if type in KeyGenerators:
            return type.value()
        raise ValueError(f"Invalid key generator type: {type}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# endregion
