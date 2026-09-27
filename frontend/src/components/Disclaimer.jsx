export default function Disclaimer({ text }) {
  return (
    <aside className="disclaimer">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" className="disclaimer-icon">
        <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5"/>
        <line x1="8" y1="7" x2="8" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        <circle cx="8" cy="5" r="0.75" fill="currentColor"/>
      </svg>
      <p className="disclaimer-text">{text}</p>
    </aside>
  );
}
