import { useState } from 'react';
import Header from './components/Header';
import ScanButton from './components/ScanButton';
import SummaryCards from './components/SummaryCards';
import RiskTable from './components/RiskTable';
import RiskChart from './components/RiskChart';
import FileDetail from './components/FileDetail';
import Disclaimer from './components/Disclaimer';
import MemoryPage from './components/MemoryPage';
import './styles/app.css';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  const [view, setView] = useState('dashboard'); // 'dashboard' | 'memory'

  // Dashboard state
  const [status,       setStatus]       = useState('idle');
  const [errorMsg,     setErrorMsg]     = useState('');
  const [scanData,     setScanData]     = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

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
        throw new Error(err.detail || `Server error: ${res.status}`);
      }

      const data = await res.json();
      setScanData(data);
      setStatus('done');
    } catch (e) {
      const msg = e.message.includes('Failed to fetch')
        ? 'Cannot reach the backend. Make sure the server is running:\n  uvicorn backend.main:app --reload'
        : e.message;
      setErrorMsg(msg);
      setStatus('error');
    }
  }

  const counts = scanData
    ? {
        total:   scanData.summary.files_scanned,
        avgRisk: scanData.summary.average_risk,
        high:    scanData.files.filter((f) => f.risk_level === 'High').length,
        medium:  scanData.files.filter((f) => f.risk_level === 'Medium').length,
        low:     scanData.files.filter((f) => f.risk_level === 'Low').length,
      }
    : null;

  return (
    <div className="app">
      <Header>
        {/* Nav tabs rendered inside Header via children */}
        <nav className="nav-tabs">
          <button
            className={`nav-tab ${view === 'dashboard' ? 'nav-tab--active' : ''}`}
            onClick={() => setView('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={`nav-tab ${view === 'memory' ? 'nav-tab--active' : ''}`}
            onClick={() => setView('memory')}
          >
            Verified Memory
          </button>
        </nav>
      </Header>

      <main className="main">
        {view === 'memory' ? (
          <MemoryPage />
        ) : (
          <>
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

                <div className="content-grid">
                  <section className="section">
                    <h2 className="section-title">Risk by File</h2>
                    <RiskChart files={scanData.files} />
                  </section>

                  <section className="section">
                    <h2 className="section-title">File Details</h2>
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
