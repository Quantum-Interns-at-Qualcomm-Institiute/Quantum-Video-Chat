/**
 * Socket.io-client singleton.
 *
 * The browser connects directly to the Python middleware server.
 * When the middleware serves the frontend, the Socket.IO connection
 * targets the same origin (host:port) the page was loaded from.
 *
 * For development or manual override, use a ?port= query parameter:
 *   http://localhost:5001              → middleware on :5001 (same origin)
 *   http://localhost:5001?port=5002    → middleware on :5002 (cross-origin)
 */
import { io, Socket } from 'socket.io-client';

/** Resolve the middleware URL: same origin by default, ?port= override. */
function getMiddlewareUrl(): { port: number; url: string } {
  if (typeof window !== 'undefined' && window.location?.search) {
    const params = new URLSearchParams(window.location.search);
    const p = params.get('port');
    if (p && !isNaN(Number(p))) {
      const port = Number(p);
      return { port, url: `http://localhost:${port}` };
    }
  }
  // When served by the middleware, connect back to the same origin
  if (typeof window !== 'undefined' && window.location?.origin && !window.location.origin.includes('undefined')) {
    const port = parseInt(window.location.port || '5001', 10);
    return { port, url: window.location.origin };
  }
  const port = parseInt(process.env.MIDDLEWARE_PORT ?? '5001', 10);
  return { port, url: `http://localhost:${port}` };
}

const { port: MIDDLEWARE_PORT, url: MIDDLEWARE_URL } = getMiddlewareUrl();

let _socket: Socket | null = null;

/** Returns the shared socket instance, creating it lazily on first call. */
export function getSocket(): Socket {
  if (!_socket) {
    _socket = io(MIDDLEWARE_URL, {
      autoConnect: false,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 20,
    });
  }
  return _socket;
}

/** Returns the port number the middleware is connected to. */
export function getMiddlewareInfo(): { port: number; url: string } {
  return { port: MIDDLEWARE_PORT, url: MIDDLEWARE_URL };
}

/** Connect (or reconnect) to the middleware. */
export function connectMiddleware(): Socket {
  const s = getSocket();
  if (!s.connected) s.connect();
  return s;
}
