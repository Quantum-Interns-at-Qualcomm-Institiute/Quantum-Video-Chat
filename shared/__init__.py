"""Shared utilities for the QVC project."""


def find_available_port(host: str = "127.0.0.1") -> int:
    """Bind to port 0 and let the OS assign an available port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]
