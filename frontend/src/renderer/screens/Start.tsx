import { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { ClientContext } from '../utils/ClientContext';
import { getSocket } from '../utils/socket';
import Header from '../components/Header';
import './Start.css';

type ConnectStatus = 'idle' | 'connecting' | 'connected' | 'error';

// Env vars baked in by webpack EnvironmentPlugin (set to '' when client-only)
const ENV_HOST = process.env.QUANTUM_SERVER_HOST ?? '';
const ENV_PORT = parseInt(process.env.QUANTUM_SERVER_PORT ?? '5050', 10);

export default function Start() {
  const navigate = useNavigate();
  const client   = useContext(ClientContext);

  const [host,    setHost]    = useState(ENV_HOST);
  const [port,    setPort]    = useState(ENV_PORT);
  const [status,  setStatus]  = useState<ConnectStatus>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  // ── Listen for middleware welcome (overrides env defaults with Python's view) ─
  useEffect(() => {
    const socket = getSocket();

    // welcome is fired once per browser connection; use it to populate fields
    socket.on('welcome', (cfg: { host: string; port: number; isLocal: boolean }) => {
      if (cfg.host) setHost(cfg.host);
      if (cfg.port) setPort(cfg.port);
      // Auto-connect when running via `npm start` (both server+client)
      if (cfg.isLocal) {
        doConnect(cfg.host, cfg.port);
      }
    });

    socket.on('server-connected', () => {
      setStatus('connected');
      setErrorMsg('');
      // Auto-register with the server once connected
      socket.emit('create_user');
    });

    socket.on('server-error', (msg: string) => {
      setStatus('error');
      setErrorMsg(msg || 'Connection failed.');
    });

    return () => {
      socket.off('welcome');
      socket.off('server-connected');
      socket.off('server-error');
    };
  }, []);

  const doConnect = (h: string, p: number) => {
    if (!h) { setErrorMsg('Please enter a server address.'); setStatus('error'); return; }
    setStatus('connecting');
    setErrorMsg('');
    getSocket().emit('configure_server', { host: h, port: p });
  };

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    doConnect(host, port);
  };

  const isConnected = status === 'connected';

  return (
    <>
      <Header />
      <div className="start-content">
        <div className="server-form-wrapper">

          <form className="server-form" onSubmit={handleConnect}>
            <div className="server-form-row">
              <label htmlFor="server-host" className="server-form-label">Server</label>
              <input
                id="server-host"
                type="text"
                className="server-input server-input--host"
                placeholder="192.168.x.x"
                value={host}
                onChange={(e) => { setHost(e.target.value); setStatus('idle'); }}
                spellCheck={false}
                autoComplete="off"
                disabled={status === 'connecting'}
              />
              <span className="server-form-colon">:</span>
              <input
                id="server-port"
                type="number"
                className="server-input server-input--port"
                placeholder="5050"
                value={port}
                min={1}
                max={65535}
                onChange={(e) => { setPort(Number(e.target.value)); setStatus('idle'); }}
                disabled={status === 'connecting'}
              />
              <button
                type="submit"
                className={`btn connect-button connect-button--${status}`}
                disabled={status === 'connecting'}
              >
                {status === 'connecting' ? 'Connecting…'
                 : status === 'connected' ? '✓ Connected'
                 : 'Connect'}
              </button>
            </div>

            {errorMsg && <p className="server-form-error">{errorMsg}</p>}
            {client.userId && (
              <p className="server-form-info">
                Your ID: <code>{client.userId}</code>
              </p>
            )}
          </form>

          {client.waitingForPeer ? (
            <div className="waiting-for-peer">
              <p className="waiting-label">Waiting for peer to join…</p>
              <p className="server-form-info">
                Share your ID: <code>{client.userId}</code>
              </p>
              <div className="ui-spinner" />
            </div>
          ) : (
            <div className="session-buttons">
              <button
                type="button"
                className="btn"
                onClick={() => client.joinRoom()}
                disabled={!isConnected}
                title={!isConnected ? 'Connect to a server first' : ''}
              >
                Start Session
              </button>
              <button
                type="button"
                className="btn"
                onClick={() => navigate('/join')}
                disabled={!isConnected}
                title={!isConnected ? 'Connect to a server first' : ''}
              >
                Join Session
              </button>
            </div>
          )}

        </div>
      </div>
    </>
  );
}
