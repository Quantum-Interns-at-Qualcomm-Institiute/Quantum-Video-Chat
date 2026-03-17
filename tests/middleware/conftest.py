"""Middleware-layer test fixtures."""
import pytest
from unittest.mock import MagicMock
from shared.adapters import FrontendAdapter


class MockAdapter(FrontendAdapter):
    """Concrete adapter for testing."""
    def __init__(self):
        self.frames = []
        self.status_events: list = []   # list of (event, data) tuples
        self._callback = None

    def send_frame(self, data: bytes) -> None:
        self.frames.append(data)

    def send_self_frame(self, data: bytes, width: int, height: int) -> None:
        pass  # not exercised in these tests

    def on_peer_id(self, callback) -> None:
        self._callback = callback

    def send_status(self, event: str, data: dict = None) -> None:
        self.status_events.append((event, data or {}))


@pytest.fixture
def mock_adapter():
    return MockAdapter()


@pytest.fixture
def mock_sio():
    return MagicMock()
