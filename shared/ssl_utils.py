"""SSL/TLS context helpers for dev certificate discovery."""

import os
from pathlib import Path


def get_ssl_context():
    """Return (certfile, keyfile) tuple if dev certs exist, else None."""
    cert_dir = os.environ.get("DEV_CERT_DIR", ".certs")
    if not cert_dir:
        return None
    cert = Path(cert_dir) / "cert.pem"
    key = Path(cert_dir) / "key.pem"
    if cert.exists() and key.exists():
        return (str(cert), str(key))
    return None
