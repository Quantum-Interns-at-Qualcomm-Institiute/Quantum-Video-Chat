import random
from encryption import EncryptionScheme, XOR
from bitarray import bitarray
def generateKey(length):
    key = bitarray(length)
    for i in range(length):
        key[i] = random.getrandbits(1)
    return key

text = input("Enter text: ")

#text to bitstring
encoded_bytes = text.encode('utf-8')
bit_array = bitarray()
bit_array.frombytes(encoded_bytes)


print(type(bit_array))
key = generateKey(len(bit_array))

#encrypt
encrypter = XOR()
encrypted = encrypter.encrypt(bit_array,key)
key_data = (key + encrypted).to01()
print(key)
print(encrypted)
print(key_data)
decrypter = XOR()
key = bitarray(key_data[:len(key_data)//2])
data = bitarray(key_data[len(key_data)//2:])
decrypted = decrypter.decrypt(data,key)
bitstring = decrypted.to01()
bytes_data = int(bitstring, 2).to_bytes((len(bitstring) + 7) // 8, byteorder='big')
message = bytes_data.decode('utf-8')
print(message)
print(text==message)