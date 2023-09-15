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

class XOR(EncryptionScheme):

    # data and key are bitstrings with same length
    def encrypt(self, data, key):
        if len(key) != len(data):
            raise ValueError("length of data must be equal to length of key")
        ans = ""
        for i in range(len(key)):
            ans += "0" if data[i]==key[i] else "1"
        return ans
    
    # data and key are bitstrings with same length
    def decrypt(self, data, key):
        ans = ""
        for i in range(len(key)):
            ans += "0" if data[i]==key[i] else "1"
        return ans

if __name__ == "__main__":
    encoder = XOR()
    text = "0101010"
    key = "1010101"
    encoded = encoder.encrypt(text,key)
    print(encoded)
    decoded = encoder.decrypt(encoded,key)
    print(decoded)
    print(decoded==text)
    encoder.encrypt(text,"00000")