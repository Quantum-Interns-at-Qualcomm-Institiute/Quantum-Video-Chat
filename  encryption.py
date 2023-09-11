from abc import ABC, abstractmethod

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
