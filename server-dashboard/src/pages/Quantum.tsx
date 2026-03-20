import { useState, useCallback } from 'react';
import { usePolling, getServerUrl } from '../api';

interface QBERSnapshot {
  timestamp: number;
  qber: number;
  event: string;
  sifted_bits: number;
  final_key_bits: number;
  detection_rate: number;
  dark_count_fraction: number;
  duration_seconds: number;
  abort_reason: string | null;
}

interface QuantumSummary {
  total_rounds: number;
  successful_rounds: number;
  failed_rounds: number;
  intrusion_count: number;
  current_qber: number | null;
  average_qber_last_10: number;
  total_sifted_bits: number;
  total_final_bits: number;
  latest_event: string | null;
  threshold: number;
  warning_threshold: number;
}

interface QuantumMetrics {
  bb84_active: boolean;
  summary?: QuantumSummary;
  history?: QBERSnapshot[];
}

interface QuantumConfig {
  key_generator: string;
  bb84_num_raw_bits: number;
  bb84_qber_threshold: number;
  bb84_fiber_length_km: number;
  bb84_source_intensity: number;
  bb84_detector_efficiency: number;
  bb84_eavesdropper_enabled: boolean;
}

async function fetchQuantumMetrics(): Promise<QuantumMetrics> {
  const res = await fetch(`${getServerUrl()}/admin/quantum/metrics`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function fetchQuantumConfig(): Promise<QuantumConfig> {
  const res = await fetch(`${getServerUrl()}/admin/quantum/config`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function toggleEavesdropper(enabled: boolean, rate = 1.0) {
  const res = await fetch(`${getServerUrl()}/admin/quantum/eavesdropper`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled, interception_rate: rate }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function qberColor(qber: number, threshold: number): string {
  if (qber >= threshold) return 'var(--danger)';
  if (qber >= threshold * 0.45) return 'var(--warning)';
  return 'var(--success)';
}

function eventBadgeClass(event: string): string {
  switch (event) {
    case 'intrusion_detected': return 'qbadge qbadge--danger';
    case 'warning': return 'qbadge qbadge--warning';
    case 'key_generation_failed': return 'qbadge qbadge--warning';
    default: return 'qbadge qbadge--normal';
  }
}

export default function Quantum() {
  const metricsFetch = useCallback(() => fetchQuantumMetrics(), []);
  const configFetch = useCallback(() => fetchQuantumConfig(), []);

  const metrics = usePolling<QuantumMetrics>(metricsFetch, 3000);
  const config = usePolling<QuantumConfig>(configFetch, 10000);

  const [eveLoading, setEveLoading] = useState(false);

  async function handleToggleEve() {
    if (!config.data) return;
    setEveLoading(true);
    try {
      await toggleEavesdropper(!config.data.bb84_eavesdropper_enabled);
      config.refresh();
      metrics.refresh();
    } catch {
      // ignore
    } finally {
      setEveLoading(false);
    }
  }

  const s = metrics.data?.summary;
  const active = metrics.data?.bb84_active ?? false;
  const threshold = s?.threshold ?? 0.11;
  const history = metrics.data?.history ?? [];

  return (
    <div>
      <h2 className="page-title">BB84 Quantum Channel</h2>

      {metrics.error && (
        <div className="error-banner">Cannot reach server: {metrics.error}</div>
      )}

      {!active && !metrics.error && (
        <div className="q-inactive">
          <p>BB84 mode is not active. Set <code>key_generator = BB84</code> in settings.ini or use <code>QVC_KEY_GENERATOR=BB84</code> to enable.</p>
        </div>
      )}

      {active && s && (
        <>
          {/* Status badge */}
          <div className="q-status-row">
            <span className={eventBadgeClass(s.latest_event ?? 'normal')}>
              {s.latest_event === 'intrusion_detected' ? 'INTRUSION DETECTED' :
               s.latest_event === 'warning' ? 'WARNING' :
               s.latest_event === 'key_generation_failed' ? 'KEY FAILED' : 'SECURE'}
            </span>
            {s.intrusion_count > 0 && (
              <span className="q-intrusion-count">
                {s.intrusion_count} intrusion{s.intrusion_count !== 1 ? 's' : ''} detected
              </span>
            )}
          </div>

          {/* Stat cards */}
          <div className="card-grid">
            <div className="stat-card">
              <span className="stat-label">Current QBER</span>
              <span className="stat-value" style={{ color: s.current_qber != null ? qberColor(s.current_qber, threshold) : undefined }}>
                {s.current_qber != null ? `${(s.current_qber * 100).toFixed(2)}%` : '—'}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Avg QBER (last 10)</span>
              <span className="stat-value" style={{ color: qberColor(s.average_qber_last_10, threshold) }}>
                {(s.average_qber_last_10 * 100).toFixed(2)}%
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Threshold</span>
              <span className="stat-value">{(threshold * 100).toFixed(0)}%</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Total Rounds</span>
              <span className="stat-value">{s.total_rounds}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Successful</span>
              <span className="stat-value" style={{ color: 'var(--success)' }}>{s.successful_rounds}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Failed</span>
              <span className="stat-value" style={{ color: s.failed_rounds > 0 ? 'var(--danger)' : undefined }}>{s.failed_rounds}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Sifted Bits</span>
              <span className="stat-value">{s.total_sifted_bits.toLocaleString()}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Final Key Bits</span>
              <span className="stat-value">{s.total_final_bits.toLocaleString()}</span>
            </div>
          </div>

          {/* Eavesdropper toggle */}
          <div className="q-eve-section">
            <h3 className="section-heading">Eavesdropper Simulation</h3>
            <button
              className={`q-eve-btn ${config.data?.bb84_eavesdropper_enabled ? 'q-eve-btn--active' : ''}`}
              onClick={handleToggleEve}
              disabled={eveLoading}
            >
              {config.data?.bb84_eavesdropper_enabled ? 'Disable Eve' : 'Enable Eve (Intercept-Resend)'}
            </button>
            <p className="q-eve-desc">
              Simulates an eavesdropper performing an intercept-resend attack on the quantum channel.
              QBER will rise to ~25%, triggering intrusion detection and automatic key redistribution.
            </p>
          </div>

          {/* QBER history table */}
          <h3 className="section-heading">Round History</h3>
          {history.length === 0 && <p className="muted-text">No rounds yet.</p>}
          {history.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>QBER</th>
                  <th>Event</th>
                  <th>Sifted</th>
                  <th>Final</th>
                  <th>Detection Rate</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {[...history].reverse().slice(0, 30).map((snap, i) => (
                  <tr key={i}>
                    <td className="mono">{new Date(snap.timestamp * 1000).toLocaleTimeString()}</td>
                    <td className="mono" style={{ color: qberColor(snap.qber, threshold) }}>
                      {(snap.qber * 100).toFixed(2)}%
                    </td>
                    <td><span className={eventBadgeClass(snap.event)}>{snap.event.replace(/_/g, ' ')}</span></td>
                    <td className="mono">{snap.sifted_bits}</td>
                    <td className="mono">{snap.final_key_bits}</td>
                    <td className="mono">{(snap.detection_rate * 100).toFixed(1)}%</td>
                    <td className="mono">{snap.duration_seconds.toFixed(2)}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Channel config */}
          {config.data && (
            <>
              <h3 className="section-heading">Channel Configuration</h3>
              <table className="config-table">
                <tbody>
                  <tr><td className="config-key">Key Generator</td><td className="config-val mono">{config.data.key_generator}</td></tr>
                  <tr><td className="config-key">Raw Bits / Round</td><td className="config-val mono">{config.data.bb84_num_raw_bits}</td></tr>
                  <tr><td className="config-key">QBER Threshold</td><td className="config-val mono">{(config.data.bb84_qber_threshold * 100).toFixed(0)}%</td></tr>
                  <tr><td className="config-key">Fiber Length</td><td className="config-val mono">{config.data.bb84_fiber_length_km} km</td></tr>
                  <tr><td className="config-key">Source Intensity (μ)</td><td className="config-val mono">{config.data.bb84_source_intensity}</td></tr>
                  <tr><td className="config-key">Detector Efficiency</td><td className="config-val mono">{(config.data.bb84_detector_efficiency * 100).toFixed(0)}%</td></tr>
                </tbody>
              </table>
            </>
          )}
        </>
      )}

      <style>{`
        .page-title { margin-bottom: 24px; font-size: 1.5rem; font-weight: 600; }
        .error-banner { background: rgba(234,105,98,0.12); border: 1px solid var(--danger); color: #ea6962; padding: 10px 16px; margin-bottom: 20px; font-size: 0.9rem; }
        .muted-text { color: rgba(212,190,152,0.4); font-size: 0.9rem; }
        .mono { font-family: monospace; font-size: 0.85rem; }
        .section-heading { font-size: 1.1rem; margin: 24px 0 12px; font-weight: 600; }

        .q-inactive { background: rgba(212,190,152,0.04); border: 1px solid var(--card-border); padding: 24px; margin-bottom: 24px; }
        .q-inactive code { background: rgba(212,190,152,0.1); padding: 2px 6px; font-size: 0.85rem; }

        .q-status-row { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
        .q-intrusion-count { color: var(--danger); font-size: 0.85rem; }

        .qbadge { display: inline-block; padding: 4px 12px; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        .qbadge--normal { color: var(--success); background: rgba(169,182,101,0.12); }
        .qbadge--warning { color: var(--warning); background: rgba(216,166,87,0.12); }
        .qbadge--danger { color: var(--danger); background: rgba(234,105,98,0.15); }

        .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }
        .stat-card { background: var(--card-bg); border: 1px solid var(--card-border); padding: 20px; display: flex; flex-direction: column; gap: 8px; }
        .stat-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; color: rgba(212,190,152,0.5); }
        .stat-value { font-size: 1.6rem; font-weight: 700; }

        .q-eve-section { margin-bottom: 24px; }
        .q-eve-btn { padding: 8px 20px; border: 1px solid var(--card-border); background: rgba(212,190,152,0.06); color: var(--off-white); cursor: pointer; font-size: 0.9rem; font-family: inherit; transition: background 0.15s; }
        .q-eve-btn:hover { background: rgba(212,190,152,0.12); }
        .q-eve-btn--active { border-color: var(--danger); color: var(--danger); background: rgba(234,105,98,0.1); }
        .q-eve-btn--active:hover { background: rgba(234,105,98,0.18); }
        .q-eve-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .q-eve-desc { color: rgba(212,190,152,0.45); font-size: 0.85rem; margin-top: 8px; max-width: 600px; line-height: 1.5; }

        .data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
        .data-table th { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--card-border); color: rgba(212,190,152,0.5); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; }
        .data-table td { padding: 8px 12px; border-bottom: 1px solid rgba(212,190,152,0.04); }

        .config-table { border-collapse: collapse; min-width: 360px; margin-bottom: 32px; }
        .config-table tr { border-bottom: 1px solid var(--card-border); }
        .config-table tr:last-child { border-bottom: none; }
        .config-key { padding: 14px 16px; color: rgba(212,190,152,0.55); font-size: 0.9rem; font-weight: 500; width: 200px; }
        .config-val { padding: 14px 16px; font-size: 0.95rem; color: var(--off-white); }
      `}</style>
    </div>
  );
}
