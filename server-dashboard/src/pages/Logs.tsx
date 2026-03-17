import { useCallback, useEffect, useRef } from 'react';
import { fetchLogs, usePolling, LogsData } from '../api';

function classifyLine(line: string): string {
  if (line.includes('(ERROR)') || line.includes('ERROR')) return 'log-error';
  if (line.includes('(WARNING)') || line.includes('WARNING')) return 'log-warn';
  if (line.includes('(DEBUG)')) return 'log-debug';
  return 'log-info';
}

export default function Logs() {
  const logsFetch = useCallback(() => fetchLogs(300), []);
  const { data, error } = usePolling<LogsData>(logsFetch, 5000);
  const preRef = useRef<HTMLPreElement>(null);

  // Auto-scroll to bottom when new lines arrive.
  useEffect(() => {
    if (preRef.current) {
      preRef.current.scrollTop = preRef.current.scrollHeight;
    }
  }, [data]);

  return (
    <div className="logs-page">
      <h2 className="page-title">Server Logs</h2>

      {data && (
        <p className="log-file-label">
          File: <span className="mono">{data.file}</span>
        </p>
      )}

      {error && <div className="error-banner">Error: {error}</div>}

      <pre ref={preRef} className="log-viewer">
        {data?.lines.map((line, i) => (
          <span key={i} className={classifyLine(line)}>
            {line}
            {'\n'}
          </span>
        ))}
        {data?.lines.length === 0 && (
          <span className="log-empty">No log lines available.</span>
        )}
      </pre>

      <style>{`
        .logs-page {
          display: flex;
          flex-direction: column;
          height: calc(100vh - 64px);
        }
        .page-title {
          margin-bottom: 8px;
          font-size: 1.5rem;
          font-weight: 600;
        }
        .log-file-label {
          margin-bottom: 12px;
          font-size: 0.85rem;
          color: rgba(212,190,152,0.5);
        }
        .error-banner {
          background: rgba(234,105,98,0.12);
          border: 1px solid var(--danger);
          color: #ea6962;
          padding: 10px 16px;
          border-radius: 0;
          margin-bottom: 12px;
          font-size: 0.9rem;
        }
        .mono {
          font-family: monospace;
        }

        .log-viewer {
          flex: 1;
          background: rgba(0,0,0,0.3);
          border: 1px solid var(--card-border);
          border-radius: 0;
          padding: 16px;
          overflow-y: auto;
          font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
          font-size: 0.82rem;
          line-height: 1.5;
          white-space: pre-wrap;
          word-break: break-all;
        }

        .log-info { color: var(--off-white); }
        .log-debug { color: rgba(212,190,152,0.45); }
        .log-warn { color: var(--warning); }
        .log-error { color: #ea6962; }
        .log-empty { color: rgba(212,190,152,0.3); font-style: italic; }
      `}</style>
    </div>
  );
}
