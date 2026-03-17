/**
 * StatusBar — Displays user ID, room ID, middleware port, and waiting state.
 *
 * Single responsibility: session status display.
 */
import { getMiddlewareInfo } from '../utils/socket';

interface StatusBarProps {
  userId:         string;
  roomId:         string;
  waitingForPeer: boolean;
}

export default function StatusBar({ userId, roomId, waitingForPeer }: StatusBarProps) {
  const mwInfo  = getMiddlewareInfo();
  const visible = waitingForPeer || !!roomId || !!userId || mwInfo.port !== 5001;

  if (!visible) return null;

  return (
    <div className="status-bar">
      {mwInfo.port !== 5001 && (
        <span className="status-chip status-chip--mw">
          Middleware: <strong>:{mwInfo.port}</strong>
        </span>
      )}
      {userId && (
        <span className="status-chip">
          User: <strong>{userId}</strong>
        </span>
      )}
      {roomId && (
        <span className="status-chip">
          Room: <strong>{roomId}</strong>
        </span>
      )}
      {waitingForPeer && (
        <span className="status-chip status-chip--waiting">
          <span className="waiting-spinner" />
          Waiting for peer to join...
        </span>
      )}
    </div>
  );
}
