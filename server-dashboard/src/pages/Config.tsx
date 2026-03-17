import { useCallback } from 'react';
import { fetchStatus, usePolling, StatusData } from '../api';

export default function Config() {
  const statusFetch = useCallback(() => fetchStatus(), []);
  const { data, error } = usePolling<StatusData>(statusFetch, 10000);

  const configRows = data
    ? [
        ['Local IP', data.config.local_ip],
        ['REST Port', String(data.config.rest_port)],
        ['WebSocket Port', String(data.config.websocket_port)],
      ]
    : [];

  return (
    <div>
      <h2 className="page-title">Server Config</h2>

      {error && <div className="error-banner">Error: {error}</div>}

      {!data && !error && <p className="muted-text">Loading…</p>}

      {data && (
        <table className="config-table">
          <tbody>
            {configRows.map(([key, value]) => (
              <tr key={key}>
                <td className="config-key">{key}</td>
                <td className="config-val mono">{value}</td>
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
        .error-banner {
          background: rgba(234,105,98,0.12);
          border: 1px solid var(--danger);
          color: #ea6962;
          padding: 10px 16px;
          border-radius: 0;
          margin-bottom: 20px;
          font-size: 0.9rem;
        }
        .muted-text {
          color: rgba(212,190,152,0.4);
          font-size: 0.9rem;
        }
        .mono {
          font-family: monospace;
        }

        .config-table {
          border-collapse: collapse;
          min-width: 360px;
        }
        .config-table tr {
          border-bottom: 1px solid var(--card-border);
        }
        .config-table tr:last-child {
          border-bottom: none;
        }
        .config-key {
          padding: 14px 16px;
          color: rgba(212,190,152,0.55);
          font-size: 0.9rem;
          font-weight: 500;
          width: 200px;
        }
        .config-val {
          padding: 14px 16px;
          font-size: 0.95rem;
          color: var(--off-white);
        }
      `}</style>
    </div>
  );
}
