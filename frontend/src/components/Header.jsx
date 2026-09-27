export default function Header({ onNavChange, activeView, backendOnline }) {
  const statusColor = backendOnline === null ? '#64748b' : backendOnline ? '#4ade80' : '#ef4444';
  const statusLabel = backendOnline === null ? 'Checking…' : backendOnline ? 'Online' : 'Offline';

  return (
    <header className="header">
      <div className="header-inner">
        <div className="header-logo">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <rect width="32" height="32" rx="8" fill="#2563eb" />
            <path d="M8 24 L16 8 L24 24" stroke="white" strokeWidth="2.4"
              strokeLinecap="round" strokeLinejoin="round" fill="none"/>
            <line x1="10.5" y1="18.5" x2="21.5" y2="18.5" stroke="white"
              strokeWidth="2.4" strokeLinecap="round"/>
            <circle cx="16" cy="27" r="1.5" fill="#60a5fa"/>
          </svg>
        </div>

        <div className="header-brand">
          <h1 className="header-title">CodeGuard AI</h1>
          <p className="header-subtitle">Find risk · Verify fixes · Remember knowledge</p>
        </div>

        <nav className="nav-tabs">
          <button
            className={`nav-tab ${activeView === 'dashboard' ? 'nav-tab--active' : ''}`}
            onClick={() => onNavChange('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={`nav-tab ${activeView === 'memory' ? 'nav-tab--active' : ''}`}
            onClick={() => onNavChange('memory')}
          >
            Verified Memory
          </button>
          <button
            className={`nav-tab ${activeView === 'guide' ? 'nav-tab--active' : ''}`}
            onClick={() => onNavChange('guide')}
          >
            Demo Guide
          </button>
        </nav>

        <div className="header-status" title={`Backend server: ${statusLabel}`}>
          <span className="header-status-dot" style={{ background: statusColor }} />
          <span className="header-status-label">Backend {statusLabel}</span>
        </div>
      </div>
    </header>
  );
}
