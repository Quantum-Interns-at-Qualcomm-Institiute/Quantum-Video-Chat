/**
 * useConnection — Manages middleware and QKD server connectivity state.
 *
 * Single responsibility: socket connection lifecycle.
 * Accepts an optional socket factory for dependency injection (testing).
 */
import { useState, useEffect } from 'react';
import { Socket } from 'socket.io-client';
import { connectMiddleware } from '../utils/socket';

export interface ConnectionState {
  middlewareConnected: boolean;
  serverConnected:     boolean;
  setServerConnected:  (v: boolean) => void;
}

/**
 * @param socketFactory — Optional factory returning a connected Socket.
 *        Defaults to ``connectMiddleware``. Pass a custom factory in tests.
 */
export function useConnection(
  socketFactory: () => Socket = connectMiddleware,
): ConnectionState {
  const [middlewareConnected, setMiddlewareConnected] = useState(false);
  const [serverConnected, setServerConnected]         = useState(false);

  useEffect(() => {
    const socket = socketFactory();

    socket.on('connect', () => setMiddlewareConnected(true));
    socket.on('disconnect', () => {
      setMiddlewareConnected(false);
      setServerConnected(false);
    });
    socket.on('connect_error', () => setMiddlewareConnected(false));
    socket.on('welcome', () => setMiddlewareConnected(true));
    socket.on('server-connected', () => setServerConnected(true));

    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('connect_error');
      socket.off('welcome');
      socket.off('server-connected');
    };
  }, []);

  return { middlewareConnected, serverConnected, setServerConnected };
}
