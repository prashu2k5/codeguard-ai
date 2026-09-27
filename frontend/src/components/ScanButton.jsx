export default function ScanButton({ status, onScan }) {
  const isLoading = status === 'loading';

  return (
    <button
      className={`scan-btn ${isLoading ? 'scan-btn--loading' : ''}`}
      onClick={onScan}
      disabled={isLoading}
    >
      {isLoading ? (
        <>
          <span className="spinner" aria-hidden="true" />
          Scanning…
        </>
      ) : (
        <>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M5 8h6M8 5v6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          Scan Repository
        </>
      )}
    </button>
  );
}
