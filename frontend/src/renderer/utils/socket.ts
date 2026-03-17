/**
 * Socket.io-client singleton.
 *
 * The browser connects directly to the Python middleware server
 * (no Electron, no IPC bridge).
 *
 * For same-device testing with two users, run two middleware instances
 * on different ports and open the app with a ?port= query parameter:
 *
 *   Tab 1: http://localhost:3000          → middleware on :5001
 *   Tab 2: http://localhost:3000?port=5002 → middleware on :5002
 */
import { io, Socket } from 'socket.io-client';

/** Read middleware port from URL search params, env var, or default 5001. */
function getMiddlewarePort(): number {
  if (typeof window !== 'undefined' && window.location?.search) {
    const params = new URLSearchParams(window.location.search);
    const p = params.get('port');
    if (p && !isNaN(Number(p))) return Number(p);
  }
  return parseInt(process.env.MIDDLEWARE_PORT ?? '5001', 10);
}

const MIDDLEWARE_PORT = getMiddlewarePort();
const MIDDLEWARE_URL  = `http://localhost:${MIDDLEWARE_PORT}`;

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
