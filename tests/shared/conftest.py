"""Shared-layer test fixtures."""
import os
import pytest
from unittest.mock import patch, mock_open

# Enable dev-only encryption modes (XOR, DEBUG) for testing
os.environ.setdefault('QVC_DEVELOPMENT', 'true')


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


@pytest.fixture
def channel_params():
    from shared.bb84.physical_layer import ChannelParameters
    return ChannelParameters()


@pytest.fixture
def bb84_protocol():
    from shared.bb84.protocol import BB84Protocol
    return BB84Protocol()


@pytest.fixture
def qber_monitor():
    from shared.bb84.qber_monitor import QBERMonitor
    return QBERMonitor()


@pytest.fixture
def bb84_key_gen():
    from shared.encryption import BB84KeyGenerator
    return BB84KeyGenerator()
