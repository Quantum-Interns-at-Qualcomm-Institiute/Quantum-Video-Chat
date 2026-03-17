import { useCallback, useState } from 'react';
import {
  fetchUsers,
  disconnectUser,
  removeUser,
  usePolling,
  UserInfo,
} from '../api';

export default function Users() {
  const usersFetch = useCallback(() => fetchUsers(), []);
  const { data: users, error, refresh } = usePolling<Record<string, UserInfo>>(
    usersFetch,
    10000,
  );
  const [actionError, setActionError] = useState<string | null>(null);

  async function handleDisconnect(userId: string) {
    try {
      setActionError(null);
      await disconnectUser(userId);
      refresh();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleRemove(userId: string) {
    try {
      setActionError(null);
      await removeUser(userId);
      refresh();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  }

  const entries = users ? Object.entries(users) : [];

  return (
    <div>
      <h2 className="page-title">Users</h2>

      {error && <div className="error-banner">Error: {error}</div>}
      {actionError && <div className="error-banner">Action failed: {actionError}</div>}

      {entries.length === 0 && !error && (
        <p className="muted-text">No users connected.</p>
      )}

      {entries.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>User ID</th>
              <th>Endpoint</th>
              <th>State</th>
              <th>Peer</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([id, user]) => (
              <tr key={id}>
                <td className="mono">{id}</td>
                <td className="mono">{user.api_endpoint}</td>
                <td>
                  <span className={`state-badge state-${user.state.toLowerCase()}`}>
                    {user.state}
                  </span>
                </td>
                <td className="mono">{user.peer ?? '—'}</td>
                <td className="actions-cell">
                  <button
                    className="action-btn disconnect-btn"
                    onClick={() => handleDisconnect(id)}
                    disabled={user.peer === null}
                    title={user.peer === null ? 'No active peer' : 'Disconnect peer'}
                  >
                    Disconnect
                  </button>
                  <button
                    className="action-btn remove-btn"
                    onClick={() => handleRemove(id)}
                    title="Remove user"
                  >
                    Remove
                  </button>
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
          vertical-align: middle;
        }
        .mono {
          font-family: monospace;
          font-size: 0.85rem;
        }

        .state-badge {
          display: inline-block;
          padding: 2px 10px;
          border-radius: 0;
          font-size: 0.8rem;
          font-weight: 600;
        }
        .state-idle {
          color: var(--success);
          background: rgba(169,182,101,0.12);
        }
        .state-connected {
          color: var(--accent);
          background: rgba(216,166,87,0.12);
        }

        .actions-cell {
          display: flex;
          gap: 6px;
        }
        .action-btn {
          padding: 4px 12px;
          border-radius: 0;
          border: 1px solid;
          background: transparent;
          cursor: pointer;
          font-size: 0.8rem;
          font-weight: 500;
        }
        .action-btn:disabled {
          opacity: 0.3;
          cursor: not-allowed;
        }
        .disconnect-btn {
          color: var(--warning);
          border-color: var(--warning);
        }
        .disconnect-btn:hover:not(:disabled) {
          background: rgba(216,166,87,0.1);
        }
        .remove-btn {
          color: var(--danger);
          border-color: var(--danger);
        }
        .remove-btn:hover:not(:disabled) {
          background: rgba(234,105,98,0.1);
        }
      `}</style>
    </div>
  );
}
