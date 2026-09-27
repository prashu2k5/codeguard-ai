export default function Header({ children }) {
  return (
    <header className="header">
      <div className="header-inner">
        <div className="header-logo">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
            <rect width="28" height="28" rx="6" fill="#2563eb" />
            <path d="M7 21 L14 7 L21 21" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
            <line x1="9.5" y1="16" x2="18.5" y2="16" stroke="white" strokeWidth="2.2" strokeLinecap="round"/>
          </svg>
        </div>
        <div>
          <h1 className="header-title">Code Health</h1>
          <p className="header-subtitle">AI-powered code risk and verified debugging</p>
        </div>
        {children && <div className="header-nav">{children}</div>}
      </div>
    </header>
  );
}
