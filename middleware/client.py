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

import argparse
import os
import signal
import sys
import requests
from flask import send_from_directory

from state import MiddlewareState, MIDDLEWARE_PORT, IS_LOCAL, DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from events import register_browser_events, register_server_events, register_rest_routes


# ─── Singleton state ──────────────────────────────────────────────────────────
mw = MiddlewareState()

# Wire up all event handlers
register_browser_events(mw)
register_server_events(mw)
register_rest_routes(mw)

# ─── Serve frontend static files ─────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist', 'renderer')

if os.path.isdir(FRONTEND_DIR):
    @mw.flask_app.route('/')
    def serve_index():
        return send_from_directory(FRONTEND_DIR, 'index.html')

    @mw.flask_app.route('/<path:path>')
    def serve_static(path):
        file_path = os.path.join(FRONTEND_DIR, path)
        if os.path.isfile(file_path):
            return send_from_directory(FRONTEND_DIR, path)
        return send_from_directory(FRONTEND_DIR, 'index.html')


# ─── Shutdown ─────────────────────────────────────────────────────────────────

def _shutdown(sig=None, _frame=None):
    print('\n(middleware): Shutting down...')
    if mw.video_thread is not None:
        mw.video_thread.stop()
    if mw.server_client.connected:
        try:
            mw.server_client.disconnect()
        except Exception:
            pass
    if mw.server_host and mw.user_id:
        try:
            requests.post(mw.server_url('/remove_user'), json={
                'user_id': mw.user_id,
            }, timeout=3)
            print(f'(middleware): Deregistered user {mw.user_id} from server.')
        except Exception:
            pass
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
        print(f'(middleware): Port {original} in use — using {chosen_port} instead')

    mw.middleware_port = chosen_port
    print(f'(middleware): Starting socket.io server on port {chosen_port}...')
    if IS_LOCAL:
        print(f'(middleware): Local mode — will auto-configure server '
              f'{DEFAULT_SERVER_HOST}:{DEFAULT_SERVER_PORT}')

    WSGIServer.reuse_addr = 1
    server = WSGIServer(('0.0.0.0', chosen_port), mw.app,
                        handler_class=WebSocketHandler, log=None)
    server.serve_forever()
