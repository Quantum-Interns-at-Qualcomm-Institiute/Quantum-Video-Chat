/**
 * useSession — Manages session state (userId, roomId, waitingForPeer).
 *
 * Single responsibility: peer session lifecycle.
 * Accepts an optional socket provider for dependency injection (testing).
 */
import { useState, useEffect, useRef } from 'react';
import { Socket } from 'socket.io-client';
import { getSocket } from '../utils/socket';

interface FrameData {
  frame: any;
  height: number;
  width: number;
  self?: boolean;
}

export interface SessionState {
  userId:         string;
  roomId:         string;
  waitingForPeer: boolean;
  setOnFrame:     (func: (data: FrameData) => void) => void;
  joinRoom:       (peer_id?: string) => Promise<any>;
  leaveRoom:      () => Promise<any>;
  /** Exposed so error handling can reset session state. */
  _setWaitingForPeer: (v: boolean) => void;
  _setRoomId:         (v: string)  => void;
}

/**
 * @param setErrorMessage — Callback to display error messages.
 * @param socketProvider — Optional function returning a Socket instance.
 *        Defaults to ``getSocket``. Pass a custom provider in tests.
 */
export function useSession(
  setErrorMessage: (msg: string) => void,
  socketProvider: () => Socket = getSocket,
): SessionState {
  const [userId, setUserId]               = useState('');
  const [roomId, _setRoomId]              = useState('');
  const [waitingForPeer, setWaitingForPeer] = useState(false);

  const onFrameRef = useRef<(data: FrameData) => void>(() => {});
  const setOnFrame = (func: (data: FrameData) => void) => {
    onFrameRef.current = func;
  };

  const joinRoom = async (peer_id?: string): Promise<any> => {
    setErrorMessage('');
    return new Promise((resolve) => {
      socketProvider().emit('join_room', peer_id ?? null, (err: any) => {
        if (err) {
          console.error('(useSession): joinRoom error —', err);
          setErrorMessage(typeof err === 'string' ? err : 'Failed to join room.');
        }
        resolve(err ?? null);
      });
    });
  };

  const leaveRoom = async (): Promise<any> => {
    setWaitingForPeer(false);
    _setRoomId('');
    setErrorMessage('');
    socketProvider().emit('leave_room');
  };

  useEffect(() => {
    const socket = socketProvider();

    socket.on('user-registered', (data: { user_id: string }) => setUserId(data.user_id));
    socket.on('waiting-for-peer', () => setWaitingForPeer(true));
    socket.on('room-id', (id: string) => {
      _setRoomId(id);
      setWaitingForPeer(false);
    });
    socket.on('frame', (data: FrameData) => onFrameRef.current(data));

    return () => {
      socket.off('user-registered');
      socket.off('waiting-for-peer');
      socket.off('room-id');
      socket.off('frame');
    };
  }, []);

  return {
    userId, roomId, waitingForPeer, setOnFrame, joinRoom, leaveRoom,
    _setWaitingForPeer: setWaitingForPeer,
    _setRoomId,
  };
}
