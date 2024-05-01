import os
import string
from abc import ABC, abstractmethod
from bitarray import bitarray
from enum import Enum
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Encryption Schemes


class AbstractEncryptionScheme(ABC):
    @abstractmethod
    def encrypt(self, data, key):
        """Encrypt the data using the provided key."""
        pass

    @abstractmethod
    def decrypt(self, data, key):
        """Decrypt the data using the provided key."""
        pass

    @abstractmethod
    def get_name(self):
        """Returns the Encryption Scheme's name."""
        pass


class XOREncryption(AbstractEncryptionScheme):

    def __init__(self):
        self.name = "XOR"

    # data and key are bit arrays with same length
    def encrypt(self, data, key):
        result = bitarray()
        for bit1, bit2 in zip(data, key):
            result.append(bit1 ^ bit2)
        return result

    # data and key are bit arrays with same length
    def decrypt(self, data, key):
        result = bitarray()
        for bit1, bit2 in zip(data, key):
            result.append(bit1 ^ bit2)
        return result

    def get_name(self):
        return self.name


class DebugEncryption(AbstractEncryptionScheme):
    def __init__(self):
        self.name = "Debug"

    def encrypt(self, data, key):
        return data

    def decrypt(self, data, key):
        return data

    def get_name(self):
        return self.name


class AESEncryption(AbstractEncryptionScheme):
    def __init__(self, bits=128):
        self.bits = bits
        self.name = f"AES-{bits}"
        self.results = []

    # data and key are bit arrays
    # using AES-CBC
    def encrypt(self, data, key):
        cipher = AES.new(key, AES.MODE_CBC, iv=b'0' * 16)
        data = pad(data, AES.block_size)
        cipheredData = cipher.encrypt(data)
        result_data = cipheredData
        return result_data

    # data and key are bit arrays
    # data contains iv and encrypted data
    def decrypt(self, data, key):
        iv = b'0' * 16
        cipheredData = data
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(cipheredData)
        decrypted = unpad(decrypted, AES.block_size)
        result = decrypted
        return result

    def get_name(self):
        return self.name


class EncryptSchemes(Enum):
    ABSTRACT = AbstractEncryptionScheme
    AES = AESEncryption
    DEBUG = DebugEncryption
    XOR = XOREncryption


class EncryptFactory:
    def create_encrypt_scheme(self, type) -> AbstractEncryptionScheme:
        if type in EncryptSchemes:
            return type.value()
        else:
            raise ValueError("Invalid encryption scheme type")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
# Key Generation


class AbstractKeyGenerator(ABC):

    @abstractmethod
    def generate_key(self, *args, **kwargs):
        """Generate a key, either randomly or preset."""
        pass

    @abstractmethod
    def get_key(self):
        """Return the generated key."""
        pass


class DebugKeyGenerator(AbstractKeyGenerator):
    def __init__(self):
        self.key: bitarray = bitarray()
        self.key_length = 0

    def speficied_keylength(self, length):
        self.key_length = length
        # Default debug key is alternating 1 and 0
        self.key = bitarray([i % 2 for i in range(self.key_length)])

    def specified_key(self, key):
        bit_array = bitarray()
        if isinstance(key, bitarray):
            bit_array = key
        elif isinstance(key, string):
            encoded_bytes = key.encode('utf-8')
            bit_array.frombytes(encoded_bytes)
        else:
            raise ValueError("Error, only bitarray or string allowed")
        self.key = bit_array
        self.length = len(key)

    def generate_key(self, key=None, key_length=0):
        if key is not None:
            self.specified_key(self, key)

        elif key_length != 0:
            self.speficied_keylength(key_length)

        else:
            raise ValueError("Invalid parameters")

    def get_key(self):
        return self.key


class RandomKeyGenerator(AbstractKeyGenerator):
    def __init__(self, key_length=0):
        self.key_length = key_length
        self.key: bitarray = None

    def generate_key(self, key_length=0):
        if key_length:
            self.key_length = key_length
        elif self.key_length < 1:
            raise ValueError("Error, please make key length nonzero")
        self.key = bitarray([int(b) for b in format(int.from_bytes(os.urandom(
            (self.key_length + 7) // 8), 'big'),
            f'0{self.key_length}b')[:self.key_length]])

    def get_key(self):
        return self.key


class FileKeyGenerator(AbstractKeyGenerator):
    def __init__(self,
                 file_name=os.path.dirname(__file__) + "/key.bin",
                 key_length=0):
        self.key_length = key_length
        self.key: bitarray = None
        self.file_name = file_name
        self.file = open(self.file_name, "rb")

    def generate_key(self, key_length=0):
        if key_length:
            self.key_length = key_length
        elif self.key_length < 1:
            raise ValueError("Error, please make key length nonzero")
        self.key = bitarray()
        self.key.frombytes(self.file.read((key_length + 7) // 8))

    def get_key(self):
        return self.key


class KeyGenerators(Enum):
    ABSTRACT = AbstractKeyGenerator
    FILE = FileKeyGenerator
    RANDOM = RandomKeyGenerator
    DEBUG = DebugKeyGenerator


class KeyGenFactory:

    def create_key_generator(self, type) -> AbstractKeyGenerator:
        if type in KeyGenerators:
            return type.value()
        else:
            raise ValueError("Invalid encryption scheme type")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class AbstractKeyExchange(ABC):

    @abstractmethod
    def get_key(self):
        """Generate a key for exchange."""
        pass

    @abstractmethod
    def send_key(self):
        """Send the generated key."""
        pass
