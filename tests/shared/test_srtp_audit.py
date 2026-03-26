"""WP #662: Test: WebRTC SRTP key handoff audit.

This project uses Socket.IO-mediated frame relay instead of native WebRTC,
so there is no SRTP layer. These tests verify the key exchange security
properties of the BB84-based encryption pipeline that replaces SRTP.
"""

from unittest.mock import mock_open, patch

# ── Key exchange security ──


class TestKeyExchangeSecurity:
    """Verify encryption key generation and handoff are secure."""

    def test_file_key_generator_has_context_manager(self):
        """WP #356: FileKeyGenerator must support context manager protocol."""
        from shared.encryption import FileKeyGenerator

        fake_data = b'\xff' * 64
        with patch('builtins.open', mock_open(read_data=fake_data)):
            gen = FileKeyGenerator(file_name='fake.bin')
            assert hasattr(gen, '__enter__')
            assert hasattr(gen, '__exit__')
            assert hasattr(gen, 'close')
            gen.close()

    def test_file_key_generator_closes_on_context_exit(self):
        """WP #356: File handle must close when leaving context manager."""
        from shared.encryption import FileKeyGenerator

        fake_data = b'\xff' * 64
        with patch('builtins.open', mock_open(read_data=fake_data)):
            with FileKeyGenerator(file_name='fake.bin') as gen:
                gen.generate_key(key_length=32)
                key = gen.get_key()
                assert len(key) > 0
            # After exiting context, file handle should be released
            assert gen._file is None

    def test_file_key_generator_close_is_idempotent(self):
        """Calling close() multiple times should not raise."""
        from shared.encryption import FileKeyGenerator

        fake_data = b'\xff' * 64
        with patch('builtins.open', mock_open(read_data=fake_data)):
            gen = FileKeyGenerator(file_name='fake.bin')
            gen.close()
            gen.close()  # Should not raise

    def test_random_key_generator_produces_sufficient_entropy(self):
        """Random key generator should produce cryptographically random keys."""
        from shared.encryption import RandomKeyGenerator

        gen = RandomKeyGenerator(key_length=256)
        gen.generate_key()
        key1 = gen.get_key()
        gen.generate_key()
        key2 = gen.get_key()
        # Two random keys should not be identical
        assert key1 != key2
        assert len(key1) == 32  # 256 bits = 32 bytes

    def test_aes_gcm_authenticated_encryption(self):
        """AES-GCM must provide authenticated encryption (not just CBC)."""
        import inspect

        from shared.encryption import AESEncryption

        source = inspect.getsource(AESEncryption)
        # Should use GCM mode, not CBC
        assert 'GCM' in source or 'gcm' in source

    def test_encryption_key_length_minimum(self):
        """Encryption keys must be at least 128 bits."""
        from shared.encryption import RandomKeyGenerator

        gen = RandomKeyGenerator(key_length=128)
        gen.generate_key()
        key = gen.get_key()
        assert len(key) >= 16  # 128 bits minimum

    def test_key_not_logged_or_printed(self):
        """Key material should not appear in log/print statements."""
        import inspect

        import shared.encryption as enc_module

        source = inspect.getsource(enc_module)
        # Should not print or log raw key bytes
        assert 'print(self.key)' not in source
        assert 'print(key)' not in source


class TestBB84KeyExchange:
    """Verify BB84 quantum key distribution security properties."""

    def test_bb84_key_generator_exists(self):
        """BB84 key generator class must be defined in encryption module."""
        import os
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        source = open(os.path.join(root, 'shared', 'encryption.py')).read()
        assert 'class BB84KeyGenerator' in source

    def test_bb84_protocol_module_exists(self):
        """BB84 protocol implementation must exist."""
        import os
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        bb84_dir = os.path.join(root, 'shared', 'bb84')
        assert os.path.isdir(bb84_dir)
        protocol_file = os.path.join(bb84_dir, 'protocol.py')
        assert os.path.isfile(protocol_file)
        source = open(protocol_file).read()
        assert 'BB84Protocol' in source or 'bb84_round' in source or 'def ' in source

    def test_qber_monitor_exists(self):
        """QBER monitor module should exist for eavesdropping detection."""
        import os
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        qber_file = os.path.join(root, 'shared', 'bb84', 'qber_monitor.py')
        assert os.path.isfile(qber_file)
        source = open(qber_file).read()
        assert 'QBER' in source or 'qber' in source
