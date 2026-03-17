/**
 * ControlBar — Server connection form, room join form, and session buttons.
 *
 * Single responsibility: user input for server/session configuration.
 */
import { useState, useEffect, useContext } from 'react';
import { ClientContext } from '../utils/ClientContext';
import { getSocket } from '../utils/socket';
import CheckIcon from './icons/CheckIcon';
import services from '../utils/services';

// Env vars baked in by webpack EnvironmentPlugin
const ENV_HOST = process.env.QUANTUM_SERVER_HOST ?? '';
const ENV_PORT = parseInt(process.env.QUANTUM_SERVER_PORT ?? '7777', 10);

type ConnectStatus = 'idle' | 'connecting' | 'connected' | 'error';

interface ControlBarProps {
  /** Whether the server is confirmed connected (from context or local state). */
  isServerConnected: boolean;
  /** Whether we're currently in an active session. */
  inSession: boolean;
}

export default function ControlBar({ isServerConnected, inSession }: ControlBarProps) {
  const client = useContext(ClientContext);

  // ── Server connection state ─────────────────────────────────────────
  const [host, setHost]         = useState(ENV_HOST);
  const [port, setPort]         = useState(ENV_PORT);
  const [connectStatus, setConnectStatus] = useState<ConnectStatus>(
    client.serverConnected ? 'connected' : 'idle'
  );
  const [connectError, setConnectError] = useState('');

  // ── Join form ───────────────────────────────────────────────────────
  const [joinId, setJoinId]       = useState('');
  const [joinError, setJoinError] = useState('');

  // ── Listen for middleware welcome + server events ───────────────────
  useEffect(() => {
    const socket = getSocket();

    const onWelcome = (cfg: { host?: string; port?: number; isLocal?: boolean }) => {
      if (cfg?.host) setHost(cfg.host);
      if (cfg?.port) setPort(cfg.port);
      if (cfg?.isLocal) {
        setConnectStatus('connecting');
        client.connectToServer(cfg.host!, cfg.port!);
      }
    };

    const onServerConnected = () => {
      setConnectStatus('connected');
      setConnectError('');
      socket.emit('create_user');
    };

    const onServerError = (msg: string) => {
      setConnectStatus('error');
      setConnectError(msg || 'Connection failed.');
    };

    socket.on('welcome', onWelcome);
    socket.on('server-connected', onServerConnected);
    socket.on('server-error', onServerError);

    return () => {
      socket.off('welcome', onWelcome);
      socket.off('server-connected', onServerConnected);
      socket.off('server-error', onServerError);
    };
  }, []);

  // ── Handlers ───────────────────────────────────────────────────────
  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    if (!host) {
      setConnectError('Please enter a server address.');
      setConnectStatus('error');
      return;
    }
    setConnectStatus('connecting');
    setConnectError('');
    client.connectToServer(host, port);
  };

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault();
    const result = services.isValidId(joinId);
    if (!result.ok) {
      setJoinError(result.error || 'Please enter a valid room ID.');
      return;
    }
    setJoinError('');
    client.joinRoom(joinId);
  };

  return (
    <>
      <div className="control-bar">
        {/* Server connection */}
        <form className="server-form" onSubmit={handleConnect}>
          <label htmlFor="server-host" className="control-label">Server</label>
          <input
            id="server-host"
            type="text"
            className="control-input control-input--host"
            placeholder="192.168.x.x"
            value={host}
            onChange={(e) => { setHost(e.target.value); setConnectStatus('idle'); }}
            spellCheck={false}
            autoComplete="off"
            disabled={connectStatus === 'connecting'}
          />
          <span className="control-colon">:</span>
          <input
            id="server-port"
            type="number"
            className="control-input control-input--port"
            placeholder="7777"
            value={port}
            min={1}
            max={65535}
            onChange={(e) => { setPort(Number(e.target.value)); setConnectStatus('idle'); }}
            disabled={connectStatus === 'connecting'}
          />
          <button
            type="submit"
            className={`button control-btn connect-btn connect-btn--${connectStatus}`}
            disabled={connectStatus === 'connecting'}
          >
            {connectStatus === 'connecting' ? 'Connecting...'
             : connectStatus === 'connected' ? <><CheckIcon size={14} /> Connected</>
             : 'Connect'}
          </button>
        </form>

        <div className="control-divider" />

        {/* Room join */}
        <form className="join-form" onSubmit={handleJoin}>
          <label htmlFor="join-room-id" className="control-label">Room</label>
          <input
            id="join-room-id"
            type="text"
            className="control-input control-input--room"
            placeholder="Room ID"
            value={joinId}
            onChange={(e) => { setJoinId(e.target.value); setJoinError(''); }}
            disabled={!isServerConnected || inSession}
            spellCheck={false}
            autoComplete="off"
          />
          <button
            type="submit"
            className="button control-btn"
            disabled={!isServerConnected || inSession}
          >
            Join
          </button>
        </form>

        <div className="control-divider" />

        {/* Session controls */}
        <button
          type="button"
          className="button control-btn start-btn"
          onClick={() => client.joinRoom()}
          disabled={!isServerConnected || inSession || client.waitingForPeer}
          title={!isServerConnected ? 'Connect to a server first' : ''}
        >
          Start Session
        </button>

        <button
          type="button"
          className="button control-btn leave-btn"
          onClick={() => client.leaveRoom()}
          disabled={!inSession && !client.waitingForPeer}
        >
          Leave
        </button>
      </div>

      {/* Inline errors */}
      {(connectError || joinError) && (
        <div className="inline-errors">
          {connectError && <span className="inline-error">{connectError}</span>}
          {joinError && <span className="inline-error">{joinError}</span>}
        </div>
      )}
    </>
  );
}
