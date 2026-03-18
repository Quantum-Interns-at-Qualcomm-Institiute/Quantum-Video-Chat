import './Loading.css';

/**
 * Transitional screen shown while waiting for:
 * - Peer connection to be established after joining a room
 *
 * Navigation away is handled by ClientContext (room-id → /session).
 */
export default function Loading() {
  return (
    <div className="loading-wrapper">
      <div className="ui-spinner" />
      <span className="loading">Connecting…</span>
    </div>
  );
}
