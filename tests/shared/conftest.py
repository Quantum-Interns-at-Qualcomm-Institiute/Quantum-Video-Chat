"""Shared-layer test fixtures."""
import pytest
from unittest.mock import patch, mock_open


@pytest.fixture
def xor_scheme():
    from shared.encryption import XOREncryption
    return XOREncryption()


@pytest.fixture
def aes_scheme():
    from shared.encryption import AESEncryption
    return AESEncryption(128)


@pytest.fixture
def debug_scheme():
    from shared.encryption import DebugEncryption
    return DebugEncryption()


@pytest.fixture
def random_key_gen():
    from shared.encryption import RandomKeyGenerator
    return RandomKeyGenerator()
