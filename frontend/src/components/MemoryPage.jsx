import { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

function IncidentCard({ incident }) {
  const [expanded, setExpanded] = useState(false);
  const date = incident.created_at
    ? new Date(incident.created_at).toLocaleString()
    : 'Unknown date';

  return (
    <div className="mem-card">
      <div className="mem-card-header" onClick={() => setExpanded(!expanded)}>
        <div className="mem-card-meta">
          <span className="mem-badge">✓ Verified</span>
          <span className="mem-file">{incident.file_path}</span>
          {incident.function_name && (
            <span className="mem-fn">→ {incident.function_name}()</span>
          )}
          <span className="mem-date">{date}</span>
        </div>
        <span className="mem-toggle">{expanded ? '▲' : '▼'}</span>
      </div>

      <p className="mem-problem">{incident.problem}</p>

      {expanded && (
        <div className="mem-detail">
          <div className="mem-section">
            <span className="mem-label">Repository</span>
            <span className="mem-value-inline">{incident.repository}</span>
          </div>
          <div className="mem-section">
            <span className="mem-label">File</span>
            <span className="mem-value-inline">{incident.file_path}</span>
          </div>
          {incident.function_name && (
            <div className="mem-section">
              <span className="mem-label">Function</span>
              <span className="mem-value-inline">{incident.function_name}()</span>
            </div>
          )}
          <div className="mem-section">
            <span className="mem-label">Root Cause</span>
            <p className="mem-value">{incident.root_cause}</p>
          </div>
          <div className="mem-section">
            <span className="mem-label">Verified Fix</span>
            <pre className="mem-code">{incident.fix}</pre>
          </div>
          {incident.regression_test && (
            <div className="mem-section">
              <span className="mem-label">Regression Test</span>
              <pre className="mem-code">{incident.regression_test}</pre>
            </div>
          )}
          <div className="mem-verify-row">
            <div className="mem-verify-stage mem-verify-stage--pass">
              <span>✅</span>
              <span>Verification Result: {incident.verification_result ?? 'PASS'}</span>
            </div>
          </div>
          <div className="mem-verified-stamp">
            ✓ Fix independently verified by automated tests (before=FAIL, after=PASS, suite=PASS)
          </div>
          <div className="mem-warning">{incident.memory_warning}</div>
        </div>
      )}
    </div>
  );
}

function SearchResult({ result }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mem-search-result">
      <div className="mem-search-result-header" onClick={() => setExpanded(!expanded)}>
        <div className="mem-result-meta">
          <span className="mem-badge">Previously Verified</span>
          <span className="mem-file">{result.file_path}</span>
          <span className="mem-relevance">
            Match: {result.relevance_score}
            <span className="mem-relevance-note"> (keyword count — not ML)</span>
          </span>
        </div>
        <span className="mem-toggle">{expanded ? '▲' : '▼'}</span>
      </div>

      <p className="mem-problem">{result.problem}</p>

      {expanded && (
        <div className="mem-detail">
          <div className="mem-search-warning">{result.memory_warning}</div>
          <div className="mem-section">
            <span className="mem-label">Root Cause</span>
            <p className="mem-value">{result.root_cause}</p>
          </div>
          <div className="mem-section">
            <span className="mem-label">Verified Fix</span>
            <pre className="mem-code">{result.fix}</pre>
          </div>
          {result.regression_test && (
            <div className="mem-section">
              <span className="mem-label">Regression Test</span>
              <pre className="mem-code">{result.regression_test}</pre>
            </div>
          )}
          <div className="mem-verified-stamp">✓ Independently verified by automated tests</div>
        </div>
      )}
    </div>
  );
}

export default function MemoryPage() {
  const [incidents,     setIncidents]    = useState([]);
  const [total,         setTotal]        = useState(0);
  const [loadStatus,    setLoadStatus]   = useState('idle');
  const [loadError,     setLoadError]    = useState('');
  const [query,         setQuery]        = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searchStatus,  setSearchStatus]  = useState('idle');
  const [searchError,   setSearchError]   = useState('');

  const loadMemory = useCallback(async () => {
    setLoadStatus('loading');
    setLoadError('');
    try {
      const res = await fetch(`${API_BASE}/memory`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      setIncidents(data.incidents ?? []);
      setTotal(data.total ?? 0);
      setLoadStatus('done');
    } catch (e) {
      const msg = e.message;
      setLoadError(
        msg.includes('fetch') || msg.includes('Failed')
          ? 'Cannot reach backend. Make sure uvicorn is running.'
          : msg
      );
      setLoadStatus('error');
    }
  }, []);

  useEffect(() => { loadMemory(); }, [loadMemory]);

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearchStatus('loading');
    setSearchError('');
    setSearchResults(null);
    try {
      const res = await fetch(`${API_BASE}/memory/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), file_path: '' }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }
      setSearchResults(await res.json());
      setSearchStatus('done');
    } catch (e) {
      setSearchError(
        e.message.includes('fetch') ? 'Cannot reach backend.' : e.message
      );
      setSearchStatus('error');
    }
  }

  function clearSearch() {
    setQuery('');
    setSearchResults(null);
    setSearchStatus('idle');
  }

  return (
    <div className="mem-page">

      {/* ── Page header ── */}
      <div className="mem-page-header">
        <div>
          <h2 className="mem-page-title">Verified Memory</h2>
          <p className="mem-page-sub">
            Evidence from fixes that passed automated verification — not guesses or AI claims.
          </p>
        </div>
        <button className="mem-refresh-btn" onClick={loadMemory} title="Refresh">
          ↺ Refresh
        </button>
      </div>

      {/* ── What is Verified Memory ── */}
      <div className="mem-what-is">
        <div className="mem-what-is-row">
          <div className="mem-what-is-item">
            <span className="mem-what-is-icon">✓</span>
            <div>
              <strong>What gets stored</strong>
              <p>Only incidents where: bug was reproduced (FAIL) → fix was applied (PASS) → full regression suite still passed (PASS).</p>
            </div>
          </div>
          <div className="mem-what-is-item">
            <span className="mem-what-is-icon">⚠</span>
            <div>
              <strong>Memory ≠ automatic truth</strong>
              <p>A stored fix worked on code at a specific point in time. Current code must always be independently re-verified before treating a fix as valid.</p>
            </div>
          </div>
          <div className="mem-what-is-item">
            <span className="mem-what-is-icon">🔍</span>
            <div>
              <strong>How it helps</strong>
              <p>When a similar bug is found, past incident context is surfaced as a starting point — with explicit re-verify warnings attached.</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Safety notice ── */}
      <div className="mem-safety-notice">
        <span className="mem-safety-icon">⚠</span>
        <p>
          <strong>Memory is evidence, not automatic truth.</strong>{' '}
          Re-check the current code before reusing any stored fix.
          A stored fix is <em>not</em> automatically verified for a new bug.
        </p>
      </div>

      {/* ── Search box ── */}
      <form className="mem-search-form" onSubmit={handleSearch}>
        <input
          className="mem-search-input"
          type="text"
          placeholder="Search verified debugging knowledge…"
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        <button className="mem-search-btn" type="submit" disabled={!query.trim()}>
          Search
        </button>
        {searchResults && (
          <button className="mem-clear-btn" type="button" onClick={clearSearch}>
            Clear
          </button>
        )}
      </form>

      {/* ── Search state ── */}
      {searchStatus === 'loading' && (
        <div className="mem-loading"><span className="spinner" /> Searching…</div>
      )}
      {searchStatus === 'error' && (
        <div className="mem-error">⚠ {searchError}</div>
      )}
      {searchStatus === 'done' && searchResults && (
        <div className="mem-search-section">
          <h3 className="mem-section-heading">
            Search: "{searchResults.query}"
            <span className="mem-count"> — {searchResults.total_matches} match{searchResults.total_matches !== 1 ? 'es' : ''}</span>
          </h3>
          <p className="mem-search-note">{searchResults.search_note}</p>
          {searchResults.total_matches === 0 ? (
            <p className="mem-empty">No matching verified incidents found.</p>
          ) : (
            searchResults.results.map(r => <SearchResult key={r.id} result={r} />)
          )}
        </div>
      )}

      {/* ── Incident count ── */}
      {loadStatus === 'done' && !searchResults && (
        <div className="mem-stats">
          <span className="mem-count-badge">{total}</span>
          <span className="mem-count-label">
            verified incident{total !== 1 ? 's' : ''} stored
          </span>
        </div>
      )}

      {/* ── Load state ── */}
      {loadStatus === 'loading' && (
        <div className="mem-loading"><span className="spinner" /> Loading memory…</div>
      )}
      {loadStatus === 'error' && (
        <div className="mem-error">⚠ {loadError}</div>
      )}

      {/* ── Incident list ── */}
      {loadStatus === 'done' && !searchResults && (
        incidents.length === 0 ? (
          <div className="mem-empty-state">
            <p className="mem-empty-title">No verified incidents stored yet.</p>
            <p className="mem-hint">
              Complete the full workflow: investigate a bug → verify the fix → click
              "Save to Verified Memory" in the verification panel.
            </p>
            <div className="mem-empty-steps">
              <span>1. Scan</span>
              <span>→</span>
              <span>2. Investigate</span>
              <span>→</span>
              <span>3. Verify Fix</span>
              <span>→</span>
              <span>4. Save to Memory</span>
            </div>
          </div>
        ) : (
          <div className="mem-list">
            {incidents.map(inc => <IncidentCard key={inc.id} incident={inc} />)}
          </div>
        )
      )}
    </div>
  );
}
