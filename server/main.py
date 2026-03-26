import os
import signal
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from rest_api import ServerAPI

from server import Server

logger = logging.getLogger(__name__)


def _shutdown(sig=None, frame=None):
    """Gracefully stop every running component and exit."""
    sig_name = signal.Signals(sig).name if sig else 'manual'
    logger.info(f"Shutting down server (signal={sig_name})...")
    ServerAPI.graceful_shutdown()
    logger.info("Exiting main program execution.\n")
    sys.exit(0)


if __name__ == '__main__':
    # Register handlers for both SIGINT (Ctrl+C) and SIGTERM (kill).
    # Using signal handlers instead of try/except KeyboardInterrupt
    # ensures shutdown works even when gevent swallows the interrupt.
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    ServerAPI.init_socketio()
    server = Server(ServerAPI.DEFAULT_ENDPOINT, socketio=ServerAPI.socketio)
    ServerAPI.init(server)


    try:
        ServerAPI.start()  # Blocking
    except KeyboardInterrupt:
        # Fallback in case signal handler didn't fire (shouldn't happen,
        # but defensive).
        logger.info("Intercepted Keyboard Interrupt.")
        _shutdown()
