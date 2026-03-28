"""Entry point for the signaling server."""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

# Ensure project root is on sys.path for shared imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shared import find_available_port  # noqa: E402
from signaling.server import create_app  # noqa: E402

logging.basicConfig(
    level=logging.DEBUG if os.environ.get("QVC_DEBUG") else logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Start the signaling server."""
    host = os.environ.get("QVC_HOST", "127.0.0.1")
    port = int(os.environ.get("QVC_SERVER_REST_PORT") or 0) or find_available_port(host)

    flask_app, _sio, _rooms = create_app()

    def _shutdown(_sig=None, _frame=None):
        sig_name = signal.Signals(_sig).name if _sig else "manual"
        logger.info("Shutting down (%s)...", sig_name)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Signaling server starting on %s:%d", host, port)

    import eventlet  # noqa: PLC0415
    import eventlet.wsgi  # noqa: PLC0415

    eventlet.wsgi.server(
        eventlet.listen((host, port)),
        flask_app.sio_wsgi_app,
        log_output=False,
    )


if __name__ == "__main__":
    main()
