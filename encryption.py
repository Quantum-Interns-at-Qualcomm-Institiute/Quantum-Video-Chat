from abc import ABC, abstractmethod
from bitarray import bitarray

class EncryptionScheme(ABC):
  
    @abstractmethod
    def encrypt(self, data, key):
        """Encrypt the data using the provided key."""
        pass

    @abstractmethod
    def decrypt(self, data, key):
        """Decrypt the data using the provided key."""
        pass
      
class KeyGenerator(ABC):
    
    @abstractmethod
    def generate_key(self, *args, **kwargs):
        """Generate a key, either randomly or preset."""
        pass

    @abstractmethod
    def get_key(self):
        """Return the generated key."""
        pass

class KeyExchange(ABC):

    @abstractmethod
    def generate_key(self):
        """Generate a key for exchange."""
        pass
    
    @abstractmethod
    def send_key(self):
        """Send the generated key."""
        pass

class XOR(EncryptionScheme):

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
