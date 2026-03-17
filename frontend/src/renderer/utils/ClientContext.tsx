/**
 * ClientContext — Composes focused hooks into a single context value.
 *
 * Single responsibility: wiring sub-hooks together and providing
 * cross-cutting event handlers (server-error, chat messages).
 */
import { useState, useEffect, createContext } from 'react';
import { getSocket } from './socket';
import { useConnection } from '../hooks/useConnection';
import { useSession }    from '../hooks/useSession';
import { useMedia }      from '../hooks/useMedia';
import type { CameraDevice, AudioDevice } from '../hooks/useMedia';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Message {
  time: string;
  name: string;
  body: string;
}

interface FrameData {
  frame: any;
  height: number;
  width: number;
  self?: boolean;
}

interface ContextValue {
  middlewareConnected: boolean;
  serverConnected:     boolean;
  userId:              string;
  status:              string;
  roomId:              string;
  cameraOn:            boolean;
  muted:               boolean;
  cameras:             CameraDevice[];
  selectedCamera:      number;
  audioDevices:        AudioDevice[];
  selectedAudio:       number;
  waitingForPeer:      boolean;
  errorMessage:        string;
  toggleCamera:        () => void;
  toggleMute:          () => void;
  selectCamera:        (deviceIndex: number) => void;
  refreshCameras:      () => void;
  selectAudio:         (deviceIndex: number) => void;
  refreshAudioDevices: () => void;
  joinRoom:            (peer_id?: string) => Promise<any>;
  leaveRoom:           () => Promise<any>;
  setOnFrame:          (func: (data: FrameData) => void) => void;
  clearError:          () => void;
  connectToServer:     (host: string, port: number) => void;
  chat: {
    messages:    Message[];
    sendMessage: (m: string) => void;
  };
}

// ─── Init ─────────────────────────────────────────────────────────────────────

const initContext: ContextValue = {
  middlewareConnected: false,
  serverConnected:     false,
  userId:              '',
  status:              'waiting',
  roomId:              '',
  cameraOn:            true,
  muted:               false,
  cameras:             [],
  selectedCamera:      0,
  audioDevices:        [],
  selectedAudio:       0,
  waitingForPeer:      false,
  errorMessage:        '',
  toggleCamera:        () => {},
  toggleMute:          () => {},
  selectCamera:        () => {},
  refreshCameras:      () => {},
  selectAudio:         () => {},
  refreshAudioDevices: () => {},
  joinRoom:            async () => {},
  leaveRoom:           async () => {},
  setOnFrame:          () => {},
  clearError:          () => {},
  connectToServer:     () => {},
  chat: {
    messages:    [],
    sendMessage: () => {},
  },
};

export const ClientContext = createContext<ContextValue>(initContext);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function ClientContextProvider({ children }: { children: React.ReactNode }) {
  // Compose focused hooks
  const connection = useConnection();
  const [errorMessage, setErrorMessage] = useState('');
  const session    = useSession(setErrorMessage);
  const media      = useMedia();

  const [status, _setStatus]     = useState(initContext.status);
  const [messages, _setMessages] = useState<Message[]>([]);

  const clearError = () => setErrorMessage('');

  const connectToServer = (host: string, port: number) => {
    setErrorMessage('');
    getSocket().emit('configure_server', { host, port });
  };

  const sendMessage = (message: string) => {
    console.log('(ClientContext): sendMessage not yet implemented', message);
  };

  // ── Cross-cutting events that span multiple hooks ────────────────────────
  useEffect(() => {
    const socket = getSocket();

    socket.on('server-error', (msg: string) => {
      connection.setServerConnected(false);
      if (msg) {
        setErrorMessage(msg);
        if (msg.toLowerCase().includes('does not exist')) {
          session._setWaitingForPeer(false);
          session._setRoomId('');
        }
      }
    });

    // Dedicated peer-disconnected event: cleanly end the session
    // without marking the server as down (server is still alive).
    socket.on('peer-disconnected', (data: { peer_id: string }) => {
      session._setWaitingForPeer(false);
      session._setRoomId('');
      setErrorMessage(`Peer ${data.peer_id} has left the session.`);
    });

    socket.on('message', (msg: Message) => {
      _setMessages((prev) => [...prev, msg]);
    });

    return () => {
      socket.off('server-error');
      socket.off('peer-disconnected');
      socket.off('message');
    };
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <ClientContext.Provider
      value={{
        middlewareConnected: connection.middlewareConnected,
        serverConnected:     connection.serverConnected,
        userId:              session.userId,
        status,
        roomId:              session.roomId,
        cameraOn:            media.cameraOn,
        muted:               media.muted,
        cameras:             media.cameras,
        selectedCamera:      media.selectedCamera,
        audioDevices:        media.audioDevices,
        selectedAudio:       media.selectedAudio,
        waitingForPeer:      session.waitingForPeer,
        errorMessage,
        toggleCamera:        media.toggleCamera,
        toggleMute:          media.toggleMute,
        selectCamera:        media.selectCamera,
        refreshCameras:      media.refreshCameras,
        selectAudio:         media.selectAudio,
        refreshAudioDevices: media.refreshAudioDevices,
        joinRoom:            session.joinRoom,
        leaveRoom:           session.leaveRoom,
        setOnFrame:          session.setOnFrame,
        clearError,
        connectToServer,
        chat: { messages, sendMessage },
      }}
    >
      {children}
    </ClientContext.Provider>
  );
}
