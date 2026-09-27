import { useState, useEffect } from 'react';

const CAPABILITIES = [
  { key: 'code_health_scan',         label: 'Code Health Scan' },
  { key: 'bug_investigation',        label: 'Bug Investigation' },
  { key: 'independent_verification', label: 'Independent Verification' },
  { key: 'verified_memory',          label: 'Verified Memory' },
  { key: 'memory_context',           label: 'Memory Context' },
  { key: 'risk_feedback_loop',       label: 'Risk Feedback Loop' },
  { key: 'cold_zone_detection',      label: 'Cold Zone Detection' },
];

export default function SystemStatus({ apiBase }) {
  const [status, setStatus]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [resetMsg, setResetMsg] = useState('');

  useEffect(() => {
    fetch(`${apiBase}/demo/status`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => { setStatus(data); setLoading(false); })
      .catch(e => {
        setError(e.message.includes('fetch') ? 'Backend offline' : e.message);
        setLoading(false);
      });
  }, [apiBase]);

  async function handleReset() {
    setResetMsg('');
    try {
      const res = await fetch(`${apiBase}/demo/reset-session`, { method: 'POST' });
      const data = await res.json();
      setResetMsg(data.message);
    } catch {
      setResetMsg('Reset failed — is backend running?');
    }
  }

  if (loading) return (
    <div className="status-panel status-panel--loading">
      <span className="spinner" /> Checking system status…
    </div>
  );

  if (error) return (
    <div className="status-panel status-panel--error">
      <span className="status-offline-icon">✕</span>
      <div>
        <strong>Backend Offline</strong>
        <p className="status-error-msg">
          Start the backend first:<br />
          <code>uvicorn backend.main:app --reload</code>
        </p>
      </div>
    </div>
  );

  const caps = status?.capabilities ?? {};

  return (
    <div className="status-panel">
      <div className="status-panel-header">
        <div>
          <span className="status-panel-title">CodeGuard AI — System Status</span>
          <span className="status-panel-version">v{status?.version ?? '1.0.0'}</span>
        </div>
        <div className="status-panel-actions">
          {status?.verified_incidents_stored != null && (
            <span className="status-mem-count">
              {status.verified_incidents_stored} verified incident{status.verified_incidents_stored !== 1 ? 's' : ''} in memory
            </span>
          )}
          <button className="status-reset-btn" onClick={handleReset} title="Reset session investigation state for a clean demo">
            ↺ Reset Session
          </button>
        </div>
      </div>

      {resetMsg && <div className="status-reset-msg">{resetMsg}</div>}

      <div className="status-capabilities">
        {CAPABILITIES.map(({ key, label }) => {
          const cap = caps[key];
          const ok = cap?.status === 'operational';
          return (
            <div key={key} className="status-cap-row" title={cap?.description ?? ''}>
              <span className={`status-cap-icon ${ok ? 'status-cap-icon--ok' : 'status-cap-icon--warn'}`}>
                {ok ? '✓' : '?'}
              </span>
              <span className="status-cap-label">{label}</span>
              {cap?.description && (
                <span className="status-cap-desc">{cap.description}</span>
              )}
            </div>
          );
        })}
      </div>

      <p className="status-disclaimer">{status?.disclaimer}</p>
    </div>
  );
}
