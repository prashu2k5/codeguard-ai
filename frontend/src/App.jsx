import { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import ScanButton from './components/ScanButton';
import SummaryCards from './components/SummaryCards';
import RiskChart from './components/RiskChart';
import RiskTable from './components/RiskTable';
import FileDetail from './components/FileDetail';
import Disclaimer from './components/Disclaimer';
import MemoryPage from './components/MemoryPage';
import DemoGuide from './components/DemoGuide';
import SystemStatus from './components/SystemStatus';
import './styles/app.css';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  const [view, setView] = useState('dashboard'); // 'dashboard' | 'memory' | 'guide'

  // Dashboard state
  const [status,       setStatus]       = useState('idle');
  const [errorMsg,     setErrorMsg]     = useState('');
  const [scanData,     setScanData]     = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [backendOnline, setBackendOnline] = useState(null); // null=unknown, true, false

  // Check backend on mount
  useEffect(() => {
    fetch(`${API_BASE}/`)
      .then(r => r.ok ? setBackendOnline(true) : setBackendOnline(false))
      .catch(() => setBackendOnline(false));
  }, []);

  async function handleScan() {
    setStatus('loading');
    setErrorMsg('');
    setSelectedFile(null);
    setScanData(null);

    try {
      const res = await fetch(`${API_BASE}/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: 'demo_repo' }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = err.detail || `Server error ${res.status}`;
        throw new Error(_friendlyError(detail, res.status));
      }

      const data = await res.json();
      setScanData(data);
      setStatus('done');
      setBackendOnline(true);
    } catch (e) {
      setErrorMsg(_friendlyError(e.message));
      setStatus('error');
      if (e.message.includes('reach') || e.message.includes('fetch')) {
        setBackendOnline(false);
      }
    }
  }

  function _friendlyError(msg, status) {
    if (!msg) return 'An unknown error occurred.';
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('reach')) {
      return 'Cannot reach the backend server.\n\nMake sure it is running:\n  uvicorn backend.main:app --reload\n\n(from the codeguard-ai/ directory)';
    }
    if (status === 404) return `Repository not found. Check the repo_path is correct.\n\nDetail: ${msg}`;
    if (status === 400) return `Invalid request: ${msg}`;
    if (status === 500) return `Server error: ${msg}`;
    return msg;
  }

  const counts = scanData
    ? {
        total:             scanData.summary.files_scanned,
        avgRisk:           scanData.summary.average_risk,
        high:              scanData.files.filter(f => f.risk_level === 'High').length,
        medium:            scanData.files.filter(f => f.risk_level === 'Medium').length,
        low:               scanData.files.filter(f => f.risk_level === 'Low').length,
        coldZones:         scanData.summary.cold_zone_count ?? scanData.files.filter(f => f.is_cold_zone).length,
        verifiedIncidents: scanData.files.reduce((acc, f) => acc + (f.verified_incident_count ?? 0), 0),
      }
    : null;

  return (
    <div className="app">
      <Header onNavChange={setView} activeView={view} backendOnline={backendOnline} />

      <main className="main">

        {/* ── Guide view ── */}
        {view === 'guide' && <DemoGuide onStartDemo={() => { setView('dashboard'); }} />}

        {/* ── Memory view ── */}
        {view === 'memory' && <MemoryPage />}

        {/* ── Dashboard view ── */}
        {view === 'dashboard' && (
          <>
            {/* System status — always visible when no scan yet */}
            {status === 'idle' && <SystemStatus apiBase={API_BASE} />}

            <div className="scan-row">
              <ScanButton status={status} onScan={handleScan} />
              {status === 'error' && (
                <div className="error-banner">
                  <span className="error-icon">⚠</span>
                  <pre className="error-text">{errorMsg}</pre>
                </div>
              )}
            </div>

            {status === 'done' && scanData && (
              <>
                <SummaryCards counts={counts} />

                {/* Cold zone callout */}
                {counts.coldZones > 0 && (
                  <div className="cold-zone-banner">
                    <span className="cold-zone-banner-icon">❄</span>
                    <div className="cold-zone-banner-text">
                      <strong>{counts.coldZones} Cold Zone{counts.coldZones !== 1 ? 's' : ''} detected</strong>
                      <span> — files with elevated predicted risk and no verified incident evidence yet. Click a ❄ file to investigate.</span>
                    </div>
                  </div>
                )}

                <div className="content-grid">
                  <section className="section">
                    <h2 className="section-title">
                      Predicted Risk by File
                      <span className="section-subtitle">Phase 1 heuristic estimate — complexity + churn + test gap</span>
                    </h2>
                    <RiskChart files={scanData.files} />
                  </section>

                  <section className="section">
                    <h2 className="section-title">
                      File Risk Details
                      <span className="section-subtitle">Predicted → Verified Evidence → Observed Risk</span>
                    </h2>
                    <RiskTable
                      files={scanData.files}
                      selected={selectedFile}
                      onSelect={setSelectedFile}
                    />
                  </section>
                </div>

                {selectedFile && (
                  <FileDetail
                    file={selectedFile}
                    onClose={() => setSelectedFile(null)}
                  />
                )}

                <Disclaimer text={scanData.summary.disclaimer} />
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
