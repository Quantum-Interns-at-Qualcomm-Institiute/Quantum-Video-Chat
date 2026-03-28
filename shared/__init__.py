"""Shared utilities for the QVC project."""

import socket as _socket


def find_available_port(host: str = "127.0.0.1") -> int:
    """Bind to port 0 and let the OS assign an available port."""
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]
