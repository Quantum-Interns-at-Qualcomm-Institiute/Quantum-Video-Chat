"""Server-layer test fixtures."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def dict_storage():
    from utils.user_manager import DictUserStorage
    return DictUserStorage()


@pytest.fixture
def user_manager():
    from utils.user_manager import UserManager, DictUserStorage
    return UserManager(storage=DictUserStorage())


@pytest.fixture
def mock_server():
    """Create a Server with SocketAPI mocked out.

    Server.__init__ does a late `from socket_api import SocketAPI`, so we
    patch at the module level where it's imported from.
    """
    MockSocketAPI = MagicMock()
    MockSocketAPI.DEFAULT_ENDPOINT = MagicMock()
    MockSocketAPI.DEFAULT_ENDPOINT.__iter__ = MagicMock(
        return_value=iter(('127.0.0.1', 3000)))

    with patch.dict('sys.modules', {'socket_api': MagicMock(SocketAPI=MockSocketAPI)}):
        from server import Server
        from shared.endpoint import Endpoint

        # Need to reimport since we patched the module
        import importlib
        import server as server_mod
        importlib.reload(server_mod)
        Server = server_mod.Server

        s = Server(Endpoint('127.0.0.1', 5050))
        s._SocketAPI = MockSocketAPI
        yield s
