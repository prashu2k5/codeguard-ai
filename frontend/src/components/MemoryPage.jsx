import { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

function IncidentCard({ incident }) {
  const [expanded, setExpanded] = useState(false);
  const date = new Date(incident.created_at).toLocaleString();

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
          <div className="mem-verified-stamp">
            <span>✓ Independently verified by automated tests</span>
          </div>
          <div className="mem-warning">{incident.memory_warning}</div>
        </div>
      )}
    </div>
  );
}

function SearchResult({ result }) {
  return (
    <div className="mem-search-result">
      <div className="mem-search-result-header">
        <span className="mem-badge">Previously Verified Incident</span>
        <span className="mem-relevance">
          Match score: {result.relevance_score}
          <span className="mem-relevance-note"> (keyword count, not ML)</span>
        </span>
      </div>

      <div className="mem-search-warning">{result.memory_warning}</div>

      <div className="mem-section">
        <span className="mem-label">Problem</span>
        <p className="mem-value">{result.problem}</p>
      </div>
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
      <div className="mem-verified-stamp">✓ Independently verified</div>
    </div>
  );
}

export default function MemoryPage() {
  const [incidents,    setIncidents]   = useState([]);
  const [total,        setTotal]       = useState(0);
  const [loadStatus,   setLoadStatus]  = useState('idle'); // idle|loading|done|error
  const [loadError,    setLoadError]   = useState('');

  const [query,        setQuery]       = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searchStatus,  setSearchStatus]  = useState('idle');
  const [searchError,   setSearchError]   = useState('');

  const loadMemory = useCallback(async () => {
    setLoadStatus('loading');
    setLoadError('');
    try {
      const res = await fetch(`${API_BASE}/memory`);
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setIncidents(data.incidents ?? []);
      setTotal(data.total ?? 0);
      setLoadStatus('done');
    } catch (e) {
      setLoadError(e.message.includes('Failed to fetch')
        ? 'Cannot reach backend. Is uvicorn running?' : e.message);
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
        throw new Error(err.detail || `Server error: ${res.status}`);
      }
      const data = await res.json();
      setSearchResults(data);
      setSearchStatus('done');
    } catch (e) {
      setSearchError(e.message.includes('Failed to fetch')
        ? 'Cannot reach backend.' : e.message);
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
      {/* ── Header row ── */}
      <div className="mem-page-header">
        <div>
          <h2 className="mem-page-title">Verified Memory</h2>
          <p className="mem-page-sub">
            Only incidents independently verified by automated tests are stored here.
          </p>
        </div>
        <button className="mem-refresh-btn" onClick={loadMemory} title="Refresh">
          ↺ Refresh
        </button>
      </div>

      {/* ── Safety notice ── */}
      <div className="mem-safety-notice">
        <span className="mem-safety-icon">⚠</span>
        <p>
          <strong>Memory is evidence, not automatic truth.</strong> When a previous
          incident matches a new problem, re-check the current code before reusing
          the fix. A stored fix is <em>not</em> automatically verified for a new bug.
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

      {/* ── Search results ── */}
      {searchStatus === 'loading' && (
        <div className="mem-loading"><span className="spinner" />Searching…</div>
      )}
      {searchStatus === 'error' && (
        <div className="mem-error">⚠ {searchError}</div>
      )}
      {searchStatus === 'done' && searchResults && (
        <div className="mem-search-section">
          <h3 className="mem-section-heading">
            Search results for "{searchResults.query}"
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
            verified incident{total !== 1 ? 's' : ''} in memory
          </span>
        </div>
      )}

      {/* ── Incident list ── */}
      {loadStatus === 'loading' && (
        <div className="mem-loading"><span className="spinner" />Loading memory…</div>
      )}
      {loadStatus === 'error' && (
        <div className="mem-error">⚠ {loadError}</div>
      )}
      {loadStatus === 'done' && !searchResults && (
        <>
          {incidents.length === 0 ? (
            <div className="mem-empty-state">
              <p>No verified incidents stored yet.</p>
              <p className="mem-hint">
                Complete a full investigation + verification workflow, then click
                "Save to Verified Memory" in the verification panel.
              </p>
            </div>
          ) : (
            <div className="mem-list">
              {incidents.map(inc => <IncidentCard key={inc.id} incident={inc} />)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
