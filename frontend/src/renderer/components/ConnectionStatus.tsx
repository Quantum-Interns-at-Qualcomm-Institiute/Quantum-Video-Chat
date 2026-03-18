import './ConnectionStatus.css';

// ---------------------------------------------------------------------------
// Shared type — imported by App.tsx, Start.tsx, Session.tsx
// ---------------------------------------------------------------------------

export interface ConnStatus {
    server: 'connecting' | 'connected' | 'error';
    userId?: string;
    peer: 'idle' | 'outgoing' | 'incoming' | 'connected' | 'disconnected';
    peerId?: string;
}

export const INITIAL_CONN_STATUS: ConnStatus = {
    server: 'connecting',
    peer: 'idle',
};

// ---------------------------------------------------------------------------
// ServerBadge — shows on the Start screen
// ---------------------------------------------------------------------------

interface ServerBadgeProps {
    status: ConnStatus;
}

export function ServerBadge({ status }: ServerBadgeProps) {
    const { server, userId } = status;

    const config =
        server === 'error'
            ? { dot: '●', label: 'Server unreachable', cls: 'error' }
            : server === 'connected'
            ? { dot: '●', label: userId ? `Connected · ${userId}` : 'Connected to server', cls: 'connected' }
            : { dot: '◌', label: 'Connecting to server…', cls: 'connecting' };

    return (
        <div className={`server-badge ${config.cls}`}>
            <span className="badge-dot">{config.dot}</span>
            <span className="badge-label">{config.label}</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// PeerBanner — shows on the Session screen
// ---------------------------------------------------------------------------

interface PeerBannerProps {
    status: ConnStatus;
}

export function PeerBanner({ status }: PeerBannerProps) {
    const { peer, peerId } = status;

    if (peer === 'connected') return null;

    const config =
        peer === 'disconnected'
            ? { icon: '✕', label: 'Call ended', cls: 'disconnected' }
            : peer === 'outgoing'
            ? { icon: '⟳', label: `Connecting to ${peerId}…`, cls: 'outgoing' }
            : peer === 'incoming'
            ? { icon: '↓', label: `Incoming connection from ${peerId}…`, cls: 'incoming' }
            : { icon: '◌', label: 'Waiting for peer connection…', cls: 'idle' };

    return (
        <div className={`peer-banner ${config.cls}`}>
            <span className="banner-icon">{config.icon}</span>
            <span className="banner-label">{config.label}</span>
        </div>
    );
}
