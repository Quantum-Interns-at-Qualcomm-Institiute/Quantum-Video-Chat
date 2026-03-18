"""Tests for middleware/adapters/socket_adapter.py — SocketAdapter."""
import pytest
import sys
import os
from unittest.mock import MagicMock, call

# Import directly from the middleware adapters package to avoid name clash with shared/adapters.py
_middleware_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'middleware')
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "middleware_adapters_socket_adapter",
    os.path.join(_middleware_dir, "adapters", "socket_adapter.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SocketAdapter = _mod.SocketAdapter

from shared.adapters import FrontendAdapter


class TestSocketAdapter:
    def _connected_socket(self):
        s = MagicMock()
        s.connected = True
        return s

    def _disconnected_socket(self):
        s = MagicMock()
        s.connected = False
        return s

    def test_is_frontend_adapter(self):
        adapter = SocketAdapter(self._connected_socket())
        assert isinstance(adapter, FrontendAdapter)

    # --- send_frame ---

    def test_send_frame_when_connected(self):
        mock_socket = self._connected_socket()
        adapter = SocketAdapter(mock_socket)
        data = b'\x00\x01\x02'
        adapter.send_frame(data)
        mock_socket.emit.assert_called_once_with('stream', data)

    def test_send_frame_when_disconnected_does_not_emit(self):
        mock_socket = self._disconnected_socket()
        adapter = SocketAdapter(mock_socket)
        adapter.send_frame(b'\x00\x01\x02')
        mock_socket.emit.assert_not_called()

    def test_send_frame_swallows_emit_exception(self):
        mock_socket = self._connected_socket()
        mock_socket.emit.side_effect = RuntimeError("socket gone")
        adapter = SocketAdapter(mock_socket)
        adapter.send_frame(b'data')  # must not raise

    def test_send_frame_multiple_when_connected(self):
        mock_socket = self._connected_socket()
        adapter = SocketAdapter(mock_socket)
        adapter.send_frame(b'frame1')
        adapter.send_frame(b'frame2')
        assert mock_socket.emit.call_count == 2

    # --- send_self_frame ---

    def test_send_self_frame_when_connected(self):
        mock_socket = self._connected_socket()
        adapter = SocketAdapter(mock_socket)
        adapter.send_self_frame(b'rgba', 640, 480)
        mock_socket.emit.assert_called_once_with(
            'self-frame', {'frame': b'rgba', 'width': 640, 'height': 480})

    def test_send_self_frame_when_disconnected_does_not_emit(self):
        mock_socket = self._disconnected_socket()
        adapter = SocketAdapter(mock_socket)
        adapter.send_self_frame(b'rgba', 640, 480)
        mock_socket.emit.assert_not_called()

    def test_send_self_frame_swallows_emit_exception(self):
        mock_socket = self._connected_socket()
        mock_socket.emit.side_effect = RuntimeError("socket gone")
        adapter = SocketAdapter(mock_socket)
        adapter.send_self_frame(b'data', 1, 1)  # must not raise

    # --- on_peer_id ---

    def test_on_peer_id_registers_handler(self):
        mock_socket = self._connected_socket()
        adapter = SocketAdapter(mock_socket)
        callback = MagicMock()
        adapter.on_peer_id(callback)
        mock_socket.on.assert_called_once_with('connect_to_peer')


class TestSendStatus:
    """SocketAdapter.send_status emits correctly and is safe when disconnected."""

    def _make_adapter(self, connected: bool):
        mock_socket = MagicMock()
        mock_socket.connected = connected
        return SocketAdapter(mock_socket), mock_socket

    def test_emits_when_connected(self):
        adapter, mock_socket = self._make_adapter(connected=True)
        adapter.send_status('server_connected')
        mock_socket.emit.assert_called_once_with(
            'status', {'event': 'server_connected', 'data': {}})

    def test_does_not_emit_when_disconnected(self):
        adapter, mock_socket = self._make_adapter(connected=False)
        adapter.send_status('server_connected')
        mock_socket.emit.assert_not_called()

    def test_passes_data_dict_through(self):
        adapter, mock_socket = self._make_adapter(connected=True)
        adapter.send_status('server_connected', {'user_id': 'abc99'})
        mock_socket.emit.assert_called_once_with(
            'status', {'event': 'server_connected', 'data': {'user_id': 'abc99'}})

    def test_none_data_becomes_empty_dict(self):
        adapter, mock_socket = self._make_adapter(connected=True)
        adapter.send_status('peer_connected', None)
        mock_socket.emit.assert_called_once_with(
            'status', {'event': 'peer_connected', 'data': {}})

    def test_multiple_status_events_all_emitted(self):
        adapter, mock_socket = self._make_adapter(connected=True)
        adapter.send_status('server_connecting')
        adapter.send_status('server_connected', {'user_id': 'xyz'})
        assert mock_socket.emit.call_count == 2
