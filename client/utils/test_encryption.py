import random
from bitarray import bitarray
from encryption import EncryptionFactory, EncryptionScheme, KeyGenerator, KeyGeneratorFactory

ENCRYPTION_SCHEME = "XOR"
KEY_GENERATOR_TYPE = "RANDOM" # Key alternates 0 and 1

plaintext = bitarray()
text = input("Enter text: ")
encoded_text = text.encode('utf-8')
plaintext.frombytes(encoded_text)

with EncryptionFactory() as factory:
    encryption_scheme: EncryptionScheme = factory.create_encryption_scheme(ENCRYPTION_SCHEME)

with KeyGeneratorFactory() as factory:
    key_generator: KeyGenerator = factory.create_key_generator(KEY_GENERATOR_TYPE)


key_generator.generate_key(key_length = len(plaintext))
ciphertext = encryption_scheme.encrypt(plaintext, key_generator.get_key())
payload = (key_generator.get_key() + ciphertext).to01()
decrypted = encryption_scheme.decrypt(data =bitarray(payload[len(payload)//2:]), key = bitarray(payload[:len(payload)//2]))
bitstring = decrypted.to01()
bytes_data = int(bitstring, 2).to_bytes((len(bitstring) + 7) // 8, byteorder='big')
message = bytes_data.decode('utf-8')
print(f"Same?: {text==message}")