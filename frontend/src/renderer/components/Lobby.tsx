/**
 * Lobby — Pre-join screen with self-preview, server connection, and room join.
 *
 * Modelled after Zoom's pre-call lobby: camera preview front-and-center,
 * minimal controls below, media toggles at the bottom.
 */
import { useState, useEffect, useContext, useRef } from 'react';
import { ClientContext } from '../utils/ClientContext';
import { getSocket } from '../utils/socket';
import { drawOnCanvas } from '../utils/canvas';
import CheckIcon from './icons/CheckIcon';
import CameraOnIcon from './icons/CameraOnIcon';
import CameraOffIcon from './icons/CameraOffIcon';
import MicOnIcon from './icons/MicOnIcon';
import MicOffIcon from './icons/MicOffIcon';
import NoiseCanvas from './NoiseCanvas';
import services from '../utils/services';
import './Lobby.css';

// Env vars baked in by webpack EnvironmentPlugin
const ENV_HOST = process.env.QUANTUM_SERVER_HOST ?? '192.168.1.28';
const ENV_PORT = parseInt(process.env.QUANTUM_SERVER_PORT ?? '5050', 10);

type ConnectStatus = 'idle' | 'connecting' | 'connected' | 'error';

export default function Lobby() {
  const client = useContext(ClientContext);
  const selfCanvasRef = useRef<HTMLCanvasElement>(null);

  // ── Server connection ─────────────────────────────────────────────────
  const [host, setHost] = useState(ENV_HOST);
  const [port, setPort] = useState(ENV_PORT);
  const [connectStatus, setConnectStatus] = useState<ConnectStatus>(
    client.serverConnected ? 'connected' : 'idle',
  );
  const [connectError, setConnectError] = useState('');

  // ── Room join ─────────────────────────────────────────────────────────
  const [joinId, setJoinId] = useState('');
  const [joinError, setJoinError] = useState('');

  // Track whether we've already emitted create_user in this session so that
  // a transient health-check recovery doesn't re-register as a new user.
  const registrationEmitted = useRef(false);

  // ── Route self-preview frames ─────────────────────────────────────────
  useEffect(() => {
    client.setOnFrame((canvasData: any) => {
      if (canvasData.self) {
        drawOnCanvas(selfCanvasRef.current, canvasData);
      }
    });
  }, []);

  // ── Request device lists on mount ────────────────────────────────────
  useEffect(() => {
    client.refreshCameras();
    client.refreshAudioDevices();
  }, []);

  // ── Socket event listeners ────────────────────────────────────────────
  useEffect(() => {
    const socket = getSocket();

    const onWelcome = (cfg: { host?: string; port?: number; isLocal?: boolean }) => {
      if (cfg?.host) setHost(cfg.host);
      if (cfg?.port) setPort(cfg.port);
      // Middleware (re)connected — reset registration guard so we re-register
      // if the middleware restarted and lost its user_id.
      registrationEmitted.current = false;
      if (cfg?.isLocal) {
        setConnectStatus('connecting');
        client.connectToServer(cfg.host!, cfg.port!);
      }
    };

    const onServerConnected = () => {
      setConnectStatus('connected');
      setConnectError('');
      // Guard: only emit create_user once per middleware session.
      // Without this, a transient health-check failure + recovery would
      // re-register as a fresh user, losing the active session.
      if (!registrationEmitted.current) {
        registrationEmitted.current = true;
        socket.emit('create_user');
      }
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

  // ── Handlers ──────────────────────────────────────────────────────────
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

  const isServerConnected = connectStatus === 'connected' || client.serverConnected;

  return (
    <div className="lobby">
      {/* ── Self preview ──────────────────────────────────────────────── */}
      <div className="lobby-preview">
        <canvas ref={selfCanvasRef} className="lobby-preview-canvas" />
        {!client.cameraOn && <NoiseCanvas label="Camera Off" />}
        {client.cameraOn && !client.roomId && (
          <div className="lobby-preview-placeholder">
            <CameraOnIcon size={48} className="lobby-preview-icon" />
          </div>
        )}
      </div>

      {/* ── Title ─────────────────────────────────────────────────────── */}
      <h2 className="lobby-title">QKD Video Chat</h2>

      {/* ── Server connect form ───────────────────────────────────────── */}
      <form className="lobby-form" onSubmit={handleConnect}>
        <label htmlFor="server-host" className="lobby-label">Server</label>
        <div className="lobby-server-inputs">
          <input
            id="server-host"
            type="text"
            className="lobby-input lobby-input--host"
            placeholder="192.168.x.x"
            value={host}
            onChange={(e) => { setHost(e.target.value); setConnectStatus('idle'); }}
            spellCheck={false}
            autoComplete="off"
            disabled={connectStatus === 'connecting'}
          />
          <span className="lobby-colon">:</span>
          <input
            id="server-port"
            type="number"
            className="lobby-input lobby-input--port"
            placeholder="7777"
            value={port}
            min={1}
            max={65535}
            onChange={(e) => { setPort(Number(e.target.value)); setConnectStatus('idle'); }}
            disabled={connectStatus === 'connecting'}
          />
        </div>
        <button
          type="submit"
          className={`lobby-btn lobby-connect-btn lobby-connect-btn--${connectStatus}`}
          disabled={connectStatus === 'connecting'}
        >
          {connectStatus === 'connecting'
            ? 'Connecting...'
            : connectStatus === 'connected'
              ? <><CheckIcon size={14} /> Connected</>
              : 'Connect'}
        </button>
      </form>

      {connectError && <span className="lobby-error">{connectError}</span>}

      {/* ── Room join form ────────────────────────────────────────────── */}
      <div className="lobby-divider" />

      <form className="lobby-form" onSubmit={handleJoin}>
        <label htmlFor="join-room-id" className="lobby-label">Room ID</label>
        <input
          id="join-room-id"
          type="text"
          className="lobby-input lobby-input--room"
          placeholder="Enter code or leave blank"
          value={joinId}
          onChange={(e) => { setJoinId(e.target.value); setJoinError(''); }}
          disabled={!isServerConnected}
          spellCheck={false}
          autoComplete="off"
        />
        <button
          type="submit"
          className="lobby-btn"
          disabled={!isServerConnected}
        >
          Join
        </button>
      </form>

      <button
        type="button"
        className="lobby-btn lobby-start-btn"
        onClick={() => client.joinRoom()}
        disabled={!isServerConnected || client.waitingForPeer}
      >
        {client.waitingForPeer ? 'Waiting for peer...' : 'Start Session'}
      </button>

      {joinError && <span className="lobby-error">{joinError}</span>}

      {/* ── Waiting indicator ─────────────────────────────────────────── */}
      {client.waitingForPeer && (
        <div className="lobby-waiting">
          <span className="lobby-waiting-spinner" />
          <span>Waiting for peer to join...</span>
          {client.userId && (
            <span className="lobby-user-id">Your ID: <strong>{client.userId}</strong></span>
          )}
        </div>
      )}

      {/* ── Media toggles ─────────────────────────────────────────────── */}
      <div className="lobby-media">
        <button
          className={`lobby-media-btn ${client.cameraOn ? '' : 'lobby-media-btn--off'}`}
          type="button"
          onClick={client.toggleCamera}
          title={client.cameraOn ? 'Turn camera off' : 'Turn camera on'}
        >
          {client.cameraOn ? <CameraOnIcon size={20} /> : <CameraOffIcon size={20} />}
        </button>

        <button
          className={`lobby-media-btn ${client.muted ? 'lobby-media-btn--off' : ''}`}
          type="button"
          onClick={client.toggleMute}
          title={client.muted ? 'Unmute microphone' : 'Mute microphone'}
        >
          {client.muted ? <MicOffIcon size={20} /> : <MicOnIcon size={20} />}
        </button>
      </div>

      {/* ── Camera device picker ───────────────────────────────────────── */}
      {client.cameras.length > 0 && (
        <div className="lobby-device-row">
          <label htmlFor="camera-select" className="lobby-label">Camera</label>
          <select
            id="camera-select"
            className="lobby-select"
            value={client.selectedCamera}
            onChange={(e) => client.selectCamera(Number(e.target.value))}
          >
            {client.cameras.map((cam) => (
              <option key={cam.index} value={cam.index}>
                {cam.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* ── Audio device picker ────────────────────────────────────────── */}
      {client.audioDevices.length > 0 && (
        <div className="lobby-device-row">
          <label htmlFor="audio-select" className="lobby-label">Mic</label>
          <select
            id="audio-select"
            className="lobby-select"
            value={client.selectedAudio}
            onChange={(e) => client.selectAudio(Number(e.target.value))}
          >
            {client.audioDevices.map((dev) => (
              <option key={dev.index} value={dev.index}>
                {dev.label}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
