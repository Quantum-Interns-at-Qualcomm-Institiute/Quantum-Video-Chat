"""Server-layer test fixtures."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def dict_storage():
    from utils.user_manager import DictUserStorage
    return DictUserStorage()


@pytest.fixture
def user_manager():
    from utils.user_manager import DictUserStorage, UserManager
    return UserManager(storage=DictUserStorage())


@pytest.fixture
def mock_server():
    """Create a Server with SocketAPI mocked out.

    Server.__init__ imports SocketAPI at top level, so we patch it
    at the module level where it's imported from.
    """
    MockSocketAPI = MagicMock()

    with patch('server.SocketAPI', MockSocketAPI):
        import importlib

        import server as server_mod
        from server import Server
        from shared.endpoint import Endpoint
        importlib.reload(server_mod)
        Server = server_mod.Server

        mock_socketio = MagicMock()
        s = Server(Endpoint('127.0.0.1', 5050), socketio=mock_socketio)
        yield s
