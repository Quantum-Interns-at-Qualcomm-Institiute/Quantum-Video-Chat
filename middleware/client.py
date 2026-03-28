"""Quantum Video Chat -- Python middleware (entry point).

Acts as a socket.io SERVER that the browser connects to directly.
Browser connects directly via Socket.IO.

Two-socket design:
  sio          -- socket.io server; browsers connect here
  server_client -- socket.io client; connects to the remote QKD server

Usage:
    python3 client.py [--port PORT]
"""
# gevent monkey-patch MUST come before any other imports that use threading/socket
from gevent import monkey

monkey.patch_all()

import argparse
import signal
import sys

import requests
from events import register_browser_events, register_rest_routes, register_server_events
from state import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, IS_LOCAL, MiddlewareState

from shared import find_available_port
from shared.logging import get_logger

logger = get_logger(__name__)

# --- Singleton state ---
logger.debug("Initializing MiddlewareState")
mw = MiddlewareState()

# Wire up all event handlers
logger.debug("Registering event handlers and REST routes")
register_browser_events(mw)
register_server_events(mw)
register_rest_routes(mw)
logger.debug("All handlers registered")

# --- Shutdown ---

def _shutdown(_sig=None, _frame=None):
    logger.info("Shutting down (signal=%s)...", _sig)
    if mw.video_thread is not None:
        logger.debug("Stopping video thread")
        mw.video_thread.stop()
    if mw.audio_thread is not None:
        logger.debug("Stopping audio thread")
        mw.audio_thread.stop()
    if mw.server_client.connected:
        logger.debug("Disconnecting server_client")
        try:
            mw.server_client.disconnect()
        except (ConnectionError, OSError):
            logger.debug("Ignoring error during server_client disconnect")
    if mw.server_host and mw.user_id:
        logger.debug("Deregistering user %s from server", mw.user_id)
        try:
            requests.post(mw.server_url("/remove_user"), json={
                "user_id": mw.user_id,
            }, timeout=3)
            logger.info("Deregistered user %s from server", mw.user_id)
        except (ConnectionError, OSError, requests.RequestException):
            logger.debug("Failed to deregister user during shutdown")
    logger.info("Shutdown complete")
    sys.exit(0)


# --- Entry point ---

if __name__ == "__main__":
    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    parser = argparse.ArgumentParser(description="QVC Python middleware server")
    parser.add_argument("--port", type=int, default=0,
                        help="Port for browsers to connect to (0 = auto-detect)")
    args = parser.parse_args()

    from gevent.pywsgi import WSGIServer
    from geventwebsocket.handler import WebSocketHandler

    chosen_port = args.port or find_available_port()

    mw.middleware_port = chosen_port
    logger.info("Starting socket.io server on port %s...", chosen_port)
    if IS_LOCAL:
        logger.info("Local mode -- will auto-configure server %s:%s",
                     DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT)

    from shared.ssl_utils import get_ssl_context as _get_ssl_context

    ssl_ctx = _get_ssl_context()
    ssl_args = {"certfile": ssl_ctx[0], "keyfile": ssl_ctx[1]} if ssl_ctx else {}
    WSGIServer.reuse_addr = 1
    server = WSGIServer(
        ("0.0.0.0", chosen_port),  # noqa: S104 -- intentional bind to all interfaces for LAN access
        mw.app,
        handler_class=WebSocketHandler, log=None, **ssl_args,
    )
    server.serve_forever()
