"""Server entry point -- initializes and runs the QKD server."""

import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rest_api import ServerAPI

from server import Server
from shared.logging import get_logger

logger = get_logger(__name__)


def _shutdown(_sig=None, _frame=None):
    """Gracefully stop every running component and exit."""
    sig_name = signal.Signals(_sig).name if _sig else "manual"
    logger.info("Shutting down server (signal=%s)...", sig_name)
    ServerAPI.graceful_shutdown()
    logger.info("Exiting main program execution.\n")
    sys.exit(0)


if __name__ == "__main__":
    # Register handlers for both SIGINT (Ctrl+C) and SIGTERM (kill).
    # Using signal handlers instead of try/except KeyboardInterrupt
    # ensures shutdown works even when gevent swallows the interrupt.
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Initializing QKD server")
    logger.debug("Default endpoint: %s", ServerAPI.DEFAULT_ENDPOINT)
    ServerAPI.init_socketio()
    server = Server(ServerAPI.DEFAULT_ENDPOINT, socketio=ServerAPI.socketio)
    ServerAPI.init(server)

    logger.info("Starting QKD server (blocking)")
    try:
        ServerAPI.start()  # Blocking
    except KeyboardInterrupt:
        # Fallback in case signal handler didn't fire (shouldn't happen,
        # but defensive).
        logger.info("Intercepted Keyboard Interrupt.")
        _shutdown()
