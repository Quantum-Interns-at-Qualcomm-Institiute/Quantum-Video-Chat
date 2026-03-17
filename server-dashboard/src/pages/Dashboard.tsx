import { useState, useCallback } from 'react';
import {
  fetchStatus,
  fetchEvents,
  usePolling,
  getServerUrl,
  setServerUrl,
  StatusData,
  EventEntry,
} from '../api';

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function Dashboard() {
  const [serverInput, setServerInput] = useState(getServerUrl());

  const statusFetch = useCallback(() => fetchStatus(), []);
  const eventsFetch = useCallback(() => fetchEvents(20), []);

  const status = usePolling<StatusData>(statusFetch, 10000);
  const events = usePolling<EventEntry[]>(eventsFetch, 10000);

  function handleUrlSave() {
    setServerUrl(serverInput.replace(/\/+$/, ''));
    status.refresh();
    events.refresh();
  }

  const activeCalls = status.data?.call_count ?? 0;

  return (
    <div>
      <h2 className="page-title">Dashboard</h2>

      <div className="server-url-bar">
        <label>Server URL</label>
        <input
          type="text"
          value={serverInput}
          onChange={(e) => setServerInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleUrlSave()}
        />
        <button onClick={handleUrlSave}>Connect</button>
      </div>

      {status.error && (
        <div className="error-banner">
          Cannot reach server: {status.error}
        </div>
      )}

      <div className="card-grid">
        <div className="stat-card">
          <span className="stat-label">Uptime</span>
          <span className="stat-value">
            {status.data ? formatUptime(status.data.uptime_seconds) : '—'}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">API State</span>
          <span className="stat-value">
            {status.data?.api_state ?? '—'}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Users Online</span>
          <span className="stat-value">
            {status.data?.user_count ?? '—'}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Active Calls</span>
          <span className="stat-value">{status.data ? activeCalls : '—'}</span>
        </div>
      </div>

      <h3 className="section-heading">Recent Events</h3>
      {events.data && events.data.length === 0 && (
        <p className="muted-text">No events yet.</p>
      )}
      {events.data && events.data.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Event</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {[...events.data].reverse().map((evt, i) => (
              <tr key={i}>
                <td className="mono">
                  {new Date(evt.timestamp).toLocaleTimeString()}
                </td>
                <td>
                  <span className={`event-badge event-${evt.event}`}>
                    {evt.event}
                  </span>
                </td>
                <td className="mono">
                  {Object.entries(evt)
                    .filter(([k]) => k !== 'timestamp' && k !== 'event')
                    .map(([k, v]) => `${k}=${v}`)
                    .join(', ')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <style>{`
        .page-title {
          margin-bottom: 24px;
          font-size: 1.5rem;
          font-weight: 600;
        }

        .server-url-bar {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 24px;
        }
        .server-url-bar label {
          font-size: 0.85rem;
          color: rgba(212,190,152,0.6);
        }
        .server-url-bar input {
          flex: 1;
          max-width: 360px;
          padding: 6px 10px;
          border: 1px solid var(--card-border);
          border-radius: 0;
          background: rgba(212,190,152,0.04);
          color: var(--off-white);
          font-family: monospace;
          font-size: 0.9rem;
        }
        .server-url-bar button {
          padding: 6px 16px;
          border: 1px solid var(--accent);
          border-radius: 0;
          background: transparent;
          color: var(--accent);
          cursor: pointer;
          font-size: 0.85rem;
        }
        .server-url-bar button:hover {
          background: rgba(216,166,87,0.1);
        }

        .error-banner {
          background: rgba(234,105,98,0.12);
          border: 1px solid var(--danger);
          color: #ea6962;
          padding: 10px 16px;
          border-radius: 0;
          margin-bottom: 20px;
          font-size: 0.9rem;
        }

        .card-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
          gap: 16px;
          margin-bottom: 32px;
        }
        .stat-card {
          background: var(--card-bg);
          border: 1px solid var(--card-border);
          border-radius: 0;
          padding: 20px;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .stat-label {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: rgba(212,190,152,0.5);
        }
        .stat-value {
          font-size: 1.6rem;
          font-weight: 700;
        }

        .section-heading {
          font-size: 1.1rem;
          margin-bottom: 12px;
          font-weight: 600;
        }

        .muted-text {
          color: rgba(212,190,152,0.4);
          font-size: 0.9rem;
        }

        .data-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 0.9rem;
        }
        .data-table th {
          text-align: left;
          padding: 8px 12px;
          border-bottom: 1px solid var(--card-border);
          color: rgba(212,190,152,0.5);
          font-weight: 600;
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .data-table td {
          padding: 8px 12px;
          border-bottom: 1px solid rgba(212,190,152,0.04);
        }
        .mono {
          font-family: monospace;
          font-size: 0.85rem;
        }

        .event-badge {
          display: inline-block;
          padding: 2px 8px;
          border-radius: 0;
          font-size: 0.8rem;
          font-weight: 600;
          background: rgba(212,190,152,0.08);
        }
        .event-user_added { color: var(--success); background: rgba(169,182,101,0.12); }
        .event-user_removed { color: var(--warning); background: rgba(216,166,87,0.12); }
        .event-peer_connected { color: var(--accent); background: rgba(216,166,87,0.12); }
        .event-peer_disconnected { color: var(--danger); background: rgba(234,105,98,0.12); }
      `}</style>
    </div>
  );
}
