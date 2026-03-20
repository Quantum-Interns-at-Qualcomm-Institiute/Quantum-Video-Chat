"""Tests for shared/encryption.py — encryption schemes, key generators, factories."""
import os
import pytest
from unittest.mock import patch, mock_open, MagicMock
from shared.encryption import (
    XOREncryption, DebugEncryption, AESEncryption,
    EncryptSchemes, EncryptFactory,
    RandomKeyGenerator, DebugKeyGenerator, FileKeyGenerator,
    KeyGenerators, KeyGenFactory,
    AbstractEncryptionScheme, AbstractKeyGenerator,
    create_encrypt_scheme, create_key_generator,
    register_encrypt_scheme, register_key_generator,
)


# ---- Encryption Schemes ----

class TestXOREncryption:
    def test_encrypt_decrypt_roundtrip(self, xor_scheme):
        data = b'\xb2\x69\xff\x00'
        key = b'\x69\xb2\x00\xff'
        encrypted = xor_scheme.encrypt(data, key)
        decrypted = xor_scheme.decrypt(encrypted, key)
        assert decrypted == data

    def test_symmetry(self, xor_scheme):
        data = b'\xf0\xf0'
        key = b'\xaa\xaa'
        assert xor_scheme.encrypt(data, key) == xor_scheme.decrypt(data, key)

    def test_xor_correctness(self, xor_scheme):
        data = b'\xc0'    # 11000000
        key = b'\xa0'     # 10100000
        result = xor_scheme.encrypt(data, key)
        assert result == b'\x60'  # 01100000

    def test_key_repeats_for_longer_data(self, xor_scheme):
        data = b'\xff\xff\xff\xff'
        key = b'\x0f'
        result = xor_scheme.encrypt(data, key)
        assert result == b'\xf0\xf0\xf0\xf0'

    def test_get_name(self, xor_scheme):
        assert xor_scheme.get_name() == 'XOR'


class TestDebugEncryption:
    def test_encrypt_passthrough(self, debug_scheme):
        data = b'hello world'
        key = b'anything'
        assert debug_scheme.encrypt(data, key) == data

    def test_decrypt_passthrough(self, debug_scheme):
        data = b'hello world'
        key = b'anything'
        assert debug_scheme.decrypt(data, key) == data

    def test_get_name(self, debug_scheme):
        assert debug_scheme.get_name() == 'Debug'


class TestAESEncryption:
    def test_encrypt_decrypt_roundtrip(self, aes_scheme):
        key = b'0123456789abcdef'  # 16 bytes = 128 bits
        plaintext = b'Hello, World!!!'  # 15 bytes, will be padded
        encrypted = aes_scheme.encrypt(plaintext, key)
        decrypted = aes_scheme.decrypt(encrypted, key)
        assert decrypted == plaintext

    def test_encrypted_differs_from_plaintext(self, aes_scheme):
        key = b'0123456789abcdef'
        plaintext = b'Test data 12345'
        encrypted = aes_scheme.encrypt(plaintext, key)
        assert encrypted != plaintext

    def test_get_name(self, aes_scheme):
        assert aes_scheme.get_name() == 'AES-128'

    def test_custom_bits(self):
        scheme = AESEncryption(256)
        assert scheme.get_name() == 'AES-256'

    def test_nonce_and_tag_prepended_to_ciphertext(self, aes_scheme):
        key = b'0123456789abcdef'
        plaintext = b'Hello, World!!!'  # 15 bytes, no padding needed with GCM
        encrypted = aes_scheme.encrypt(plaintext, key)
        # 12 bytes nonce + 16 bytes tag + 15 bytes ciphertext
        assert len(encrypted) == 12 + 16 + len(plaintext)

    def test_different_nonces_produce_different_ciphertext(self, aes_scheme):
        key = b'0123456789abcdef'
        plaintext = b'Same data same data same!'
        enc1 = aes_scheme.encrypt(plaintext, key)
        enc2 = aes_scheme.encrypt(plaintext, key)
        assert enc1 != enc2
        assert aes_scheme.decrypt(enc1, key) == plaintext
        assert aes_scheme.decrypt(enc2, key) == plaintext

    def test_nonce_is_random_bytes(self, aes_scheme):
        key = b'0123456789abcdef'
        plaintext = b'test data.......'
        enc1 = aes_scheme.encrypt(plaintext, key)
        enc2 = aes_scheme.encrypt(plaintext, key)
        nonce1 = enc1[:12]
        nonce2 = enc2[:12]
        assert nonce1 != nonce2

    def test_tampered_ciphertext_raises(self, aes_scheme):
        key = b'0123456789abcdef'
        plaintext = b'authenticated data'
        encrypted = aes_scheme.encrypt(plaintext, key)
        # Flip a bit in the ciphertext portion
        tampered = bytearray(encrypted)
        tampered[-1] ^= 0x01
        with pytest.raises(Exception):
            aes_scheme.decrypt(bytes(tampered), key)

    def test_tampered_tag_raises(self, aes_scheme):
        key = b'0123456789abcdef'
        plaintext = b'authenticated data'
        encrypted = aes_scheme.encrypt(plaintext, key)
        # Flip a bit in the tag
        tampered = bytearray(encrypted)
        tampered[12] ^= 0x01
        with pytest.raises(Exception):
            aes_scheme.decrypt(bytes(tampered), key)


# ---- Encrypt Factory (deprecated) ----

class TestEncryptFactory:
    def test_create_aes(self):
        factory = EncryptFactory()
        scheme = factory.create_encrypt_scheme(EncryptSchemes.AES)
        assert isinstance(scheme, AESEncryption)

    def test_create_xor(self):
        factory = EncryptFactory()
        scheme = factory.create_encrypt_scheme(EncryptSchemes.XOR)
        assert isinstance(scheme, XOREncryption)

    def test_create_debug(self):
        factory = EncryptFactory()
        scheme = factory.create_encrypt_scheme(EncryptSchemes.DEBUG)
        assert isinstance(scheme, DebugEncryption)

    def test_invalid_type_raises(self):
        factory = EncryptFactory()
        with pytest.raises(ValueError, match="Invalid encryption"):
            factory.create_encrypt_scheme("INVALID")

    def test_context_manager(self):
        with EncryptFactory() as factory:
            scheme = factory.create_encrypt_scheme(EncryptSchemes.DEBUG)
            assert isinstance(scheme, DebugEncryption)


# ---- Registry Functions ----

class TestEncryptRegistry:
    def test_create_aes(self):
        scheme = create_encrypt_scheme('AES')
        assert isinstance(scheme, AESEncryption)

    def test_create_xor(self):
        scheme = create_encrypt_scheme('XOR')
        assert isinstance(scheme, XOREncryption)

    def test_create_debug(self):
        scheme = create_encrypt_scheme('DEBUG')
        assert isinstance(scheme, DebugEncryption)

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Invalid encryption"):
            create_encrypt_scheme('NONEXISTENT')

    def test_register_custom_scheme(self):
        class CustomScheme(AbstractEncryptionScheme):
            def encrypt(self, data, key): return data
            def decrypt(self, data, key): return data
            def get_name(self): return 'Custom'

        register_encrypt_scheme('CUSTOM', CustomScheme)
        scheme = create_encrypt_scheme('CUSTOM')
        assert isinstance(scheme, CustomScheme)


class TestKeygenRegistry:
    def test_create_random(self):
        gen = create_key_generator('RANDOM')
        assert isinstance(gen, RandomKeyGenerator)

    def test_create_debug(self):
        gen = create_key_generator('DEBUG')
        assert isinstance(gen, DebugKeyGenerator)

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Invalid key generator"):
            create_key_generator('NONEXISTENT')

    def test_register_custom_generator(self):
        class CustomGen(AbstractKeyGenerator):
            def generate_key(self, **kwargs): pass
            def get_key(self): return b'\x00'

        register_key_generator('CUSTOM', CustomGen)
        gen = create_key_generator('CUSTOM')
        assert isinstance(gen, CustomGen)


# ---- Key Generators ----

class TestRandomKeyGenerator:
    def test_generate_returns_bytes(self, random_key_gen):
        random_key_gen.generate_key(key_length=128)
        key = random_key_gen.get_key()
        assert isinstance(key, bytes)

    def test_generate_correct_byte_length(self, random_key_gen):
        random_key_gen.generate_key(key_length=128)
        key = random_key_gen.get_key()
        assert len(key) == 16  # 128 bits = 16 bytes

    def test_different_keys(self, random_key_gen):
        random_key_gen.generate_key(key_length=128)
        key1 = random_key_gen.get_key()
        random_key_gen.generate_key(key_length=128)
        key2 = random_key_gen.get_key()
        # Extremely unlikely to be equal with 128 random bits
        assert key1 != key2

    def test_zero_length_raises(self):
        gen = RandomKeyGenerator()
        with pytest.raises(ValueError, match="nonzero"):
            gen.generate_key(key_length=0)

    def test_constructor_key_length(self):
        gen = RandomKeyGenerator(key_length=256)
        gen.generate_key()
        key = gen.get_key()
        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits = 32 bytes


class TestDebugKeyGenerator:
    def test_specified_keylength(self):
        gen = DebugKeyGenerator()
        gen.specified_keylength(8)
        key = gen.get_key()
        assert isinstance(key, bytes)
        assert len(key) == 8
        # Alternating pattern: 0,1,0,1,0,1,0,1
        assert key == bytes([0, 1, 0, 1, 0, 1, 0, 1])

    def test_specified_keylength_shorter(self):
        gen = DebugKeyGenerator()
        gen.specified_keylength(4)
        assert gen.get_key() == bytes([0, 1, 0, 1])


class TestFileKeyGenerator:
    def test_generate_key_reads_file(self):
        fake_data = b'\xff\x00\xaa'
        with patch('builtins.open', mock_open(read_data=fake_data)):
            gen = FileKeyGenerator(file_name='fake_key.bin')
            gen.generate_key(key_length=16)
            key = gen.get_key()
            assert isinstance(key, bytes)

    def test_default_file_path(self):
        with patch('builtins.open', mock_open(read_data=b'\x00' * 32)):
            gen = FileKeyGenerator()
            assert gen.file_name.endswith('key.bin')


# ---- Key Gen Factory (deprecated) ----

class TestKeyGenFactory:
    def test_create_random(self):
        factory = KeyGenFactory()
        gen = factory.create_key_generator(KeyGenerators.RANDOM)
        assert isinstance(gen, RandomKeyGenerator)

    def test_create_debug(self):
        factory = KeyGenFactory()
        gen = factory.create_key_generator(KeyGenerators.DEBUG)
        assert isinstance(gen, DebugKeyGenerator)

    def test_invalid_type_raises(self):
        factory = KeyGenFactory()
        with pytest.raises(ValueError, match="Invalid key generator"):
            factory.create_key_generator("INVALID")

    def test_context_manager(self):
        with KeyGenFactory() as factory:
            gen = factory.create_key_generator(KeyGenerators.RANDOM)
            assert isinstance(gen, RandomKeyGenerator)


# ---- Encrypt Schemes Enum ----

class TestEncryptSchemesEnum:
    def test_aes_maps_to_class(self):
        assert EncryptSchemes.AES.value is AESEncryption

    def test_xor_maps_to_class(self):
        assert EncryptSchemes.XOR.value is XOREncryption

    def test_debug_maps_to_class(self):
        assert EncryptSchemes.DEBUG.value is DebugEncryption


class TestKeyGeneratorsEnum:
    def test_random_maps_to_class(self):
        assert KeyGenerators.RANDOM.value is RandomKeyGenerator

    def test_debug_maps_to_class(self):
        assert KeyGenerators.DEBUG.value is DebugKeyGenerator

    def test_file_maps_to_class(self):
        assert KeyGenerators.FILE.value is FileKeyGenerator
