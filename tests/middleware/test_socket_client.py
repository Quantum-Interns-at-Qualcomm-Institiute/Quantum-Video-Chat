"""Tests for middleware/client/socket_client.py — SocketClient class."""
import pytest
from unittest.mock import MagicMock, patch
from shared.endpoint import Endpoint


def _make_client(**overrides):
    """Create a SocketClient instance with AV mocked out."""
    with patch('client.socket_client.AV') as MockAV:
        MockAV.return_value = MagicMock()
        MockAV.return_value.client_namespaces = {'/test': MagicMock()}

        from client.socket_client import SocketClient
        defaults = dict(
            endpoint=('127.0.0.1', 3000),
            user_id='user1',
            display_message=lambda u, m: None,
            adapter=MagicMock(),
        )
        defaults.update(overrides)
        sc = SocketClient(**defaults)
        sc._MockAV = MockAV
        return sc


class TestSocketClient:
    def test_init_sets_fields(self):
        sc = _make_client(user_id='user1')
        assert sc.user_id == 'user1'
        assert sc.endpoint is not None
        assert sc.av is not None

    def test_is_connected(self):
        sc = _make_client()
        sc.sio = MagicMock()
        sc.sio.connected = True
        assert sc.is_connected() is True

        sc.sio.connected = False
        assert sc.is_connected() is False

    def test_send_message(self):
        sc = _make_client(user_id='u1')
        sc.sio = MagicMock()
        sc.send_message('hello', namespace='/')
        sc.sio.send.assert_called_once_with(
            (('u1',), 'hello'), namespace='/')

    def test_disconnect(self):
        sc = _make_client()
        sc.sio = MagicMock()
        sc.disconnect()
        sc.sio.disconnect.assert_called_once()

    def test_kill_calls_disconnect(self):
        sc = _make_client()
        sc.sio = MagicMock()
        sc.kill()
        sc.sio.disconnect.assert_called_once()

    def test_connect(self):
        sc = _make_client()
        sc.sio = MagicMock()
        sc.sio.connected = False
        sc.connect()
        sc.sio.connect.assert_called_once()

    def test_connect_skips_when_already_connected(self):
        sc = _make_client()
        sc.sio = MagicMock()
        sc.sio.connected = True
        sc.connect()
        sc.sio.connect.assert_not_called()

    def test_connect_catches_connection_error(self):
        """ConnectionError during sio.connect is caught and logged."""
        import socketio as sio_lib
        sc = _make_client()
        sc.sio = MagicMock()
        sc.sio.connected = False
        sc.sio.connect.side_effect = sio_lib.exceptions.ConnectionError("refused")
        # Should not raise
        sc.connect()

    def test_start_calls_connect(self):
        """start() delegates to connect()."""
        sc = _make_client()
        sc.sio = MagicMock()
        sc.sio.connected = True  # prevent actual connect
        sc.start()
        # connect() was called but skipped due to already connected

    def test_on_connect_handler(self):
        """_on_connect runs without error."""
        sc = _make_client()
        sc._on_connect()

    def test_on_message_handler(self):
        """_on_message calls display_message."""
        msgs = []
        sc = _make_client(display_message=lambda u, m: msgs.append((u, m)))
        sc._on_message('u2', 'hello')
        assert msgs == [('u2', 'hello')]
