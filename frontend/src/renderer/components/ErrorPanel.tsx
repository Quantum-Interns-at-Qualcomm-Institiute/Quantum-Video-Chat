/**
 * ErrorPanel — Collapsible right-side error log.
 *
 * Single responsibility: display and manage error messages.
 */
import { useState, useEffect, useContext } from 'react';
import { ClientContext } from '../utils/ClientContext';

export default function ErrorPanel() {
  const client = useContext(ClientContext);
  const [open, setOpen]     = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  // Push context errors into the panel
  useEffect(() => {
    if (client.errorMessage) {
      setErrors((prev) => {
        if (prev[prev.length - 1] === client.errorMessage) return prev;
        return [...prev, client.errorMessage];
      });
      setOpen(true);
    }
  }, [client.errorMessage]);

  return (
    <div className={`error-panel ${open ? 'error-panel--open' : ''}`}>
      <button
        className="error-panel-toggle"
        onClick={() => setOpen((prev) => !prev)}
        aria-label={open ? 'Collapse error panel' : 'Expand error panel'}
        title={open ? 'Collapse' : 'Errors'}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="14" height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        {!open && errors.length > 0 && (
          <span className="error-badge">{errors.length}</span>
        )}
      </button>

      {open && (
        <div className="error-panel-body">
          <div className="error-panel-header">
            <span className="error-panel-title">Errors</span>
            <button
              className="error-panel-clear"
              onClick={() => { setErrors([]); client.clearError(); }}
              aria-label="Clear all errors"
            >
              Clear
            </button>
          </div>
          <div className="error-panel-list">
            {errors.length === 0 && (
              <span className="error-panel-empty">No errors.</span>
            )}
            {errors.map((err, i) => (
              <div key={i} className="error-panel-item">{err}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
