"""
Quantum Video Chat — Python middleware (entry point).

Acts as a socket.io SERVER that the browser connects to directly.
Browser connects directly via Socket.IO.

Two-socket design:
  sio          — socket.io server; browsers connect here (port 5001)
  server_client — socket.io client; connects to the remote QKD server

Usage:
    python3 client.py [--port 5001]
"""
# gevent monkey-patch MUST come before any other imports that use threading/socket
from gevent import monkey

monkey.patch_all()

import argparse  # noqa: E402
import signal  # noqa: E402
import sys  # noqa: E402

import requests  # noqa: E402
from events import register_browser_events, register_rest_routes, register_server_events  # noqa: E402
from state import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, IS_LOCAL, MIDDLEWARE_PORT, MiddlewareState  # noqa: E402

from shared.logging import get_logger  # noqa: E402

logger = get_logger(__name__)

# ─── Singleton state ──────────────────────────────────────────────────────────
mw = MiddlewareState()

# Wire up all event handlers
register_browser_events(mw)
register_server_events(mw)
register_rest_routes(mw)

# ─── Shutdown ─────────────────────────────────────────────────────────────────

def _shutdown(sig=None, _frame=None):
    logger.info('Shutting down...')
    if mw.video_thread is not None:
        mw.video_thread.stop()
    if mw.server_client.connected:
        try:
            mw.server_client.disconnect()
        except Exception:
            logger.debug('Ignoring error during server_client disconnect')
    if mw.server_host and mw.user_id:
        try:
            requests.post(mw.server_url('/remove_user'), json={
                'user_id': mw.user_id,
            }, timeout=3)
            logger.info('Deregistered user %s from server.', mw.user_id)
        except Exception:
            logger.debug('Failed to deregister user during shutdown')
    sys.exit(0)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    parser = argparse.ArgumentParser(description='QVC Python middleware server')
    parser.add_argument('--port', type=int, default=MIDDLEWARE_PORT,
                        help='Port for browsers to connect to (default: 5001)')
    args = parser.parse_args()

    from gevent.pywsgi import WSGIServer
    from geventwebsocket.handler import WebSocketHandler

    def _port_in_use(port: int) -> bool:
        """Check if a port is already bound by another process."""
        import socket as _s
        try:
            s = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
            s.setsockopt(_s.SOL_SOCKET, _s.SO_REUSEADDR, 0)
            s.bind(('', port))
            s.close()
            return False
        except OSError:
            return True

    chosen_port = args.port
    if _port_in_use(chosen_port):
        original = chosen_port
        while _port_in_use(chosen_port):
            chosen_port += 1
        logger.info('Port %s in use — using %s instead', original, chosen_port)

    mw.middleware_port = chosen_port
    logger.info('Starting socket.io server on port %s...', chosen_port)
    if IS_LOCAL:
        logger.info('Local mode — will auto-configure server %s:%s',
                     DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT)

    from shared.ssl_utils import get_ssl_context as _get_ssl_context

    ssl_ctx = _get_ssl_context()
    ssl_args = {"certfile": ssl_ctx[0], "keyfile": ssl_ctx[1]} if ssl_ctx else {}
    WSGIServer.reuse_addr = 1
    server = WSGIServer(('0.0.0.0', chosen_port), mw.app,
                        handler_class=WebSocketHandler, log=None, **ssl_args)
    server.serve_forever()
