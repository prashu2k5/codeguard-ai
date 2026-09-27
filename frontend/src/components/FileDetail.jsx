import { useState } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

function explain(file) {
  const parts = [];
  if (file.complexity_score >= 15) {
    parts.push(`High cyclomatic complexity (${file.complexity_score.toFixed(1)}/100) — many branching paths.`);
  } else if (file.complexity_score >= 7) {
    parts.push(`Moderate complexity (${file.complexity_score.toFixed(1)}/100) — worth monitoring.`);
  } else {
    parts.push(`Low complexity (${file.complexity_score.toFixed(1)}/100) — straightforward logic.`);
  }
  if (file.git_churn_commits >= 5) {
    parts.push(`High git churn (${file.git_churn_commits} commits) — frequently changed, higher regression risk.`);
  } else if (file.git_churn_commits >= 3) {
    parts.push(`Moderate churn (${file.git_churn_commits} commits) — has seen a few revisions.`);
  } else {
    parts.push(`Low churn (${file.git_churn_commits} commit${file.git_churn_commits !== 1 ? 's' : ''}) — stable file.`);
  }
  if (file.test_coverage_pct === 0) {
    parts.push(`No test coverage (0%) — entirely untested.`);
  } else if (file.test_coverage_pct < 60) {
    parts.push(`Low test coverage (${file.test_coverage_pct.toFixed(0)}%) — significant gaps.`);
  } else if (file.test_coverage_pct < 90) {
    parts.push(`Partial coverage (${file.test_coverage_pct.toFixed(0)}%) — some paths uncovered.`);
  } else {
    parts.push(`Strong coverage (${file.test_coverage_pct.toFixed(0)}%) — well tested.`);
  }
  return parts;
}

// ---------------------------------------------------------------------------
// Phase 7 — Verified incident evidence panel
// ---------------------------------------------------------------------------
function VerifiedIncidentEvidence({ file }) {
  const count = file.verified_incident_count ?? 0;
  const evidence = file.verified_incident_evidence ?? [];
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="detail-risk-block detail-evidence-block">
      <div className="detail-block-label">Verified Incident Evidence</div>
      <p className="evidence-source-note">
        Source: Verified Memory only — independently verified bugs (before=FAIL, after=PASS, suite=PASS).
      </p>

      {count === 0 ? (
        <p className="evidence-none">No verified incident evidence yet.</p>
      ) : (
        <>
          <p className="evidence-count">
            <strong>{count}</strong> independently verified incident{count !== 1 ? 's' : ''} recorded for this file.
          </p>
          <button
            className="evidence-toggle-btn"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? '▲ Hide incidents' : '▼ Show incidents'}
          </button>
          {expanded && evidence.map((inc, i) => (
            <div key={inc.id ?? i} className="evidence-card">
              <div className="evidence-card-header">
                <span className="evidence-verified-stamp">✓ Independently Verified</span>
                <span className="evidence-date">{inc.created_at ? new Date(inc.created_at).toLocaleDateString() : ''}</span>
              </div>
              <div className="invest-section">
                <span className="invest-label">Problem</span>
                <p className="invest-value">{inc.problem}</p>
              </div>
              <div className="invest-section">
                <span className="invest-label">Root Cause</span>
                <p className="invest-value">{inc.root_cause}</p>
              </div>
              {inc.function_name && (
                <div className="invest-section">
                  <span className="invest-label">Function</span>
                  <span className="invest-value">{inc.function_name}</span>
                </div>
              )}
              <p className="evidence-source">{inc.source}</p>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase 7 — Observed risk panel
// ---------------------------------------------------------------------------
function ObservedRiskPanel({ file }) {
  const predictedRisk = file.risk_score;
  const incidentScore = file.incident_score ?? 0;
  const observedRisk  = file.observed_risk  ?? file.risk_score;
  const observedLevel = file.observed_risk_level ?? file.risk_level;
  const LEVEL_COLOR = { High: '#ef4444', Medium: '#f59e0b', Low: '#22c55e' };
  const color = LEVEL_COLOR[observedLevel] ?? '#94a3b8';

  return (
    <div className="detail-risk-block detail-observed-block">
      <div className="detail-block-label">Observed Risk (Phase 7)</div>

      <div className="detail-score-row">
        <div className="detail-score-circle" style={{ borderColor: color }}>
          <span className="detail-score-num" style={{ color }}>{observedRisk.toFixed(1)}</span>
          <span className="detail-score-label">/ 100</span>
        </div>
        <span className={`badge badge--lg badge--${observedLevel.toLowerCase()}`}>
          {observedLevel} Risk
        </span>
        {file.is_cold_zone && (
          <span className="badge badge--cold" title="Cold Zone — predicted risk without verified incident evidence">
            ❄ Cold Zone
          </span>
        )}
      </div>

      <div className="detail-metrics">
        <div className="metric">
          <span className="metric-label">Predicted Risk</span>
          <span className="metric-value">{predictedRisk.toFixed(1)}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Incident Score</span>
          <span className="metric-value">+{incidentScore.toFixed(1)}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Verified Count</span>
          <span className="metric-value">{file.verified_incident_count ?? 0}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Observed Risk</span>
          <span className="metric-value">{observedRisk.toFixed(1)}</span>
        </div>
      </div>

      {file.risk_explanation && (
        <div className="detail-why">
          <h4 className="detail-why-title">Risk Explanation</h4>
          <p className="detail-why-text">{file.risk_explanation}</p>
        </div>
      )}

      {file.risk_formula && (
        <pre className="detail-formula">{file.risk_formula}</pre>
      )}

      <p className="detail-note">
        Observed risk = predicted risk + verified incident evidence. Heuristic estimate only.
      </p>
    </div>
  );
}

const LEVEL_COLOR      = { High: '#ef4444', Medium: '#f59e0b', Low: '#22c55e' };
const CONFIDENCE_COLOR = { High: '#16a34a', Medium: '#d97706', Low: '#dc2626' };

// ---------------------------------------------------------------------------
// Phase 6 — Similar incident card (inside InvestigationPanel)
// ---------------------------------------------------------------------------
function SimilarIncidentCard({ incident, onUseAsCandidate, isCandidate }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`ctx-card ${isCandidate ? 'ctx-card--active' : ''}`}>
      <div className="ctx-card-header" onClick={() => setExpanded(!expanded)}>
        <div className="ctx-card-meta">
          <span className="ctx-badge-prev">✓ Previously Verified</span>
          <span className="ctx-provenance">{incident.provenance_label}</span>
          <span className="ctx-match">Match score: {incident.match_score}</span>
        </div>
        <span className="ctx-toggle">{expanded ? '▲' : '▼'}</span>
      </div>

      <p className="ctx-problem">{incident.problem}</p>

      {expanded && (
        <div className="ctx-detail">
          <div className="invest-section">
            <span className="invest-label">Root Cause</span>
            <p className="invest-value ctx-text">{incident.root_cause}</p>
          </div>
          <div className="invest-section">
            <span className="invest-label">Verified Fix</span>
            <pre className="invest-code invest-fix">{incident.fix}</pre>
          </div>
          {incident.regression_test && (
            <div className="invest-section">
              <span className="invest-label">Regression Test</span>
              <pre className="invest-code">{incident.regression_test}</pre>
            </div>
          )}
          <div className="ctx-verified-stamp">✓ Independently verified by automated tests</div>
          <p className="ctx-note">{incident.match_note}</p>
        </div>
      )}

      <div className="ctx-warnings">
        <p className="ctx-warn-text">{incident.not_same_warning}</p>
        <p className="ctx-warn-text">{incident.reuse_warning}</p>
      </div>

      {!isCandidate && (
        <button className="ctx-use-btn" onClick={() => onUseAsCandidate(incident)}>
          Use as Fix Candidate
        </button>
      )}
      {isCandidate && (
        <div className="ctx-candidate-label">
          ✔ Set as candidate — requires fresh verification
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase 6 — Memory context section
// ---------------------------------------------------------------------------
function MemoryContextSection({ similar, candidate, onUseAsCandidate }) {
  const hasMatches = similar && similar.length > 0;

  return (
    <div className="ctx-section">
      <div className="ctx-section-header">
        <span className="ctx-section-title">Verified Memory Context</span>
        <span className="ctx-current-label">⚠ Current issue — Not Yet Verified</span>
      </div>

      {!hasMatches && (
        <p className="ctx-empty">No similar verified incidents found.</p>
      )}

      {hasMatches && (
        <>
          <p className="ctx-found-note">
            Similar verified incident found — previous knowledge may provide
            useful debugging context. Fresh independent verification is required.
          </p>
          {similar.map(inc => (
            <SimilarIncidentCard
              key={inc.id}
              incident={inc}
              onUseAsCandidate={onUseAsCandidate}
              isCandidate={candidate?.id === inc.id}
            />
          ))}
        </>
      )}

      {candidate && (
        <div className="ctx-candidate-panel">
          <div className="ctx-candidate-header">
            <span className="ctx-candidate-title">Current Fix Candidate</span>
            <span className="ctx-candidate-sub">Candidate only — requires fresh verification</span>
          </div>
          <div className="ctx-provenance-row">
            <span className="ctx-badge-prev">Source: {candidate.provenance_label}</span>
            <span className="ctx-current-label">Current Investigation: New</span>
          </div>
          <p className="ctx-candidate-note">
            The fix below is derived from a previously verified incident. It has
            NOT been verified for the current codebase. Use <strong>Verify Fix</strong> to
            run independent verification before treating this as confirmed.
          </p>
          <pre className="invest-code invest-fix">{candidate.fix}</pre>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase 3 + 6 — Investigation panel (with memory context)
// ---------------------------------------------------------------------------
function InvestigationPanel({ result, onClear, onVerify, verifyStatus }) {
  const isFallback = result.mode === 'fallback-heuristic';
  const canVerify  = result.file === 'data_processor.py';
  const [candidate, setCandidate] = useState(null);

  const similar = result.similar_incidents ?? [];

  return (
    <div className="invest-panel">
      <div className="invest-header">
        <div className="invest-title-row">
          <span className="invest-tag">
            {isFallback ? '🔍 Heuristic Analysis' : '🤖 AI Investigation'}
          </span>
          <span className="invest-not-verified">Not Yet Verified</span>
        </div>
        <button className="invest-clear" onClick={onClear} title="Clear">✕</button>
      </div>

      <div className="invest-disclaimer">{result.disclaimer}</div>

      <div className="invest-section">
        <span className="invest-label">Problem</span>
        <p className="invest-value">{result.problem}</p>
      </div>
      <div className="invest-section">
        <span className="invest-label">Root Cause</span>
        <p className="invest-value">{result.root_cause}</p>
      </div>
      <div className="invest-section">
        <span className="invest-label">Evidence</span>
        <pre className="invest-code">{result.evidence}</pre>
      </div>
      <div className="invest-section">
        <span className="invest-label">Suggested Fix</span>
        <pre className="invest-code invest-fix">{result.suggested_fix}</pre>
      </div>
      <div className="invest-confidence">
        <span className="invest-label">Confidence</span>
        <span className="invest-confidence-badge"
          style={{ color: CONFIDENCE_COLOR[result.confidence] ?? '#475569' }}>
          {result.confidence}
        </span>
      </div>

      {/* Phase 6 — memory context */}
      <MemoryContextSection
        similar={similar}
        candidate={candidate}
        onUseAsCandidate={inc => setCandidate(inc)}
      />

      {canVerify && verifyStatus === 'idle' && (
        <button className="verify-btn" onClick={onVerify}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path d="M2 7l4 4 6-6" stroke="currentColor" strokeWidth="1.6"
              strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          {candidate ? 'Verify Fix (Candidate)' : 'Verify Fix'}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase 4 — Verification stage display
// ---------------------------------------------------------------------------
const STAGES = [
  { key: 'broken',   icon: '🔴', label: 'Broken code'             },
  { key: 'before',   icon: '❌', label: 'Regression test — BEFORE' },
  { key: 'fixing',   icon: '🔧', label: 'Fix applied'              },
  { key: 'after',    icon: '🟢', label: 'Regression test — AFTER'  },
  { key: 'suite',    icon: '🟢', label: 'Full test suite'          },
  { key: 'verified', icon: '✅', label: 'VERIFIED'                 },
];

function VerificationPanel({ result, file, investResult, onClear }) {
  const [expanded,    setExpanded]   = useState(null);
  const [saveStatus,  setSaveStatus] = useState('idle'); // idle|loading|done|error
  const [saveMsg,     setSaveMsg]    = useState('');

  if (!result) return null;

  const stageStatus = {
    broken:   'done',
    before:   result.before.test_result  === 'FAIL' ? 'done' : 'fail',
    fixing:   'done',
    after:    result.after.test_result   === 'PASS' ? 'done' : 'fail',
    suite:    result.regression_suite.result === 'PASS' ? 'done' : 'fail',
    verified: result.verified ? 'done' : 'fail',
  };

  const stageOutput = {
    before: result.before.output,
    after:  result.after.output,
    suite:  result.regression_suite.output,
  };

  async function handleSave() {
    setSaveStatus('loading');
    setSaveMsg('');
    try {
      const body = {
        repository:          'demo_repo',
        file_path:           file.file,
        function_name:       'normalize',
        problem:             investResult?.problem  ?? result.fix_description,
        root_cause:          investResult?.root_cause ?? '',
        fix:                 investResult?.suggested_fix ?? result.fix_description,
        regression_test:     'demo_repo/regression_normalize.py',
        before_output:       result.before.output,
        after_output:        result.after.output,
        verification_result: 'PASS',
      };
      const res = await fetch(`${API_BASE}/memory/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${res.status}`);
      }
      const data = await res.json();
      setSaveMsg(data.message);
      setSaveStatus('done');
    } catch (e) {
      setSaveMsg(e.message);
      setSaveStatus('error');
    }
  }

  return (
    <div className="verify-panel">
      <div className="verify-header">
        <div className="verify-title-row">
          <span className="verify-tag">Independent Verification</span>
          {result.verified
            ? <span className="verify-badge verify-badge--pass">Fix independently verified by automated tests</span>
            : <span className="verify-badge verify-badge--fail">Verification failed</span>
          }
        </div>
        <button className="invest-clear" onClick={onClear} title="Clear">✕</button>
      </div>

      <p className="verify-disclaimer">{result.disclaimer}</p>

      <div className="verify-stages">
        {STAGES.map(({ key, icon, label }) => {
          const st = stageStatus[key];
          const hasOutput = key in stageOutput;
          const counts = key === 'before'
            ? `${result.before.tests_failed} failed, ${result.before.tests_passed} passed`
            : key === 'after'
            ? `${result.after.tests_passed} passed`
            : key === 'suite'
            ? `${result.regression_suite.tests_passed} passed, ${result.regression_suite.tests_failed} failed`
            : '';
          return (
            <div key={key} className={`verify-stage verify-stage--${st}`}>
              <div className="verify-stage-row"
                onClick={() => hasOutput && setExpanded(expanded === key ? null : key)}>
                <span className="verify-stage-icon">{icon}</span>
                <span className="verify-stage-label">{label}</span>
                {counts && <span className="verify-stage-counts">{counts}</span>}
                {hasOutput && (
                  <span className="verify-stage-toggle">
                    {expanded === key ? '▲' : '▼'} output
                  </span>
                )}
              </div>
              {hasOutput && expanded === key && (
                <pre className="verify-output">{stageOutput[key]}</pre>
              )}
            </div>
          );
        })}
      </div>

      {result.failure_reason && (
        <div className="verify-failure-reason">
          <strong>Why not verified:</strong> {result.failure_reason}
        </div>
      )}

      {/* Save to memory — only when verified=true and not yet saved */}
      {result.verified && saveStatus === 'idle' && (
        <button className="mem-save-btn" onClick={handleSave}>
          💾 Save to Verified Memory
        </button>
      )}
      {result.verified && saveStatus === 'loading' && (
        <div className="invest-loading">
          <span className="spinner" aria-hidden="true" />Saving…
        </div>
      )}
      {saveStatus === 'done' && (
        <div className="mem-save-confirm">✓ {saveMsg}</div>
      )}
      {saveStatus === 'error' && (
        <div className="invest-error">
          ⚠ Save failed: {saveMsg}
          <button className="invest-retry" onClick={handleSave}>Retry</button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main FileDetail modal
// ---------------------------------------------------------------------------
export default function FileDetail({ file, onClose }) {
  const reasons = explain(file);
  const color   = LEVEL_COLOR[file.risk_level] ?? '#94a3b8';

  // Phase 3 — investigation state
  const [investStatus, setInvestStatus] = useState('idle');
  const [investResult, setInvestResult] = useState(null);
  const [investError,  setInvestError]  = useState('');

  // Phase 4 — verification state
  const [verifyStatus, setVerifyStatus] = useState('idle');
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifyError,  setVerifyError]  = useState('');

  async function handleInvestigate() {
    setInvestStatus('loading');
    setInvestError('');
    setInvestResult(null);
    setVerifyStatus('idle');
    setVerifyResult(null);

    try {
      const res = await fetch(`${API_BASE}/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: 'demo_repo', file_path: file.file, bug_description: '' }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${res.status}`);
      }
      setInvestResult(await res.json());
      setInvestStatus('done');
    } catch (e) {
      setInvestError(e.message.includes('Failed to fetch')
        ? 'Cannot reach backend. Is uvicorn running?' : e.message);
      setInvestStatus('error');
    }
  }

  async function handleVerify() {
    setVerifyStatus('loading');
    setVerifyError('');
    setVerifyResult(null);

    try {
      const res = await fetch(`${API_BASE}/verify-fix`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: 'demo_repo', file_path: file.file }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${res.status}`);
      }
      setVerifyResult(await res.json());
      setVerifyStatus('done');
    } catch (e) {
      setVerifyError(e.message.includes('Failed to fetch')
        ? 'Cannot reach backend. Is uvicorn running?' : e.message);
      setVerifyStatus('error');
    }
  }

  return (
    <div className="detail-overlay" onClick={onClose}>
      <div className="detail-panel" onClick={(e) => e.stopPropagation()}>

        {/* ── Header ── */}
        <div className="detail-header">
          <h3 className="detail-filename">{file.file}</h3>
          <button className="detail-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {/* ── Predicted risk (Phase 1 — unchanged) ── */}
        <div className="detail-risk-block">
          <div className="detail-block-label">Predicted Risk (Phase 1)</div>

          <div className="detail-score-row">
            <div className="detail-score-circle" style={{ borderColor: color }}>
              <span className="detail-score-num" style={{ color }}>{file.risk_score.toFixed(1)}</span>
              <span className="detail-score-label">/ 100</span>
            </div>
            <span className={`badge badge--lg badge--${file.risk_level.toLowerCase()}`}>
              {file.risk_level} Risk
            </span>
          </div>

          <div className="detail-metrics">
            <div className="metric">
              <span className="metric-label">Complexity</span>
              <span className="metric-value">{file.complexity_score.toFixed(1)}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Git Commits</span>
              <span className="metric-value">{file.git_churn_commits}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Coverage</span>
              <span className="metric-value">{file.test_coverage_pct.toFixed(0)}%</span>
            </div>
            <div className="metric">
              <span className="metric-label">Churn Score</span>
              <span className="metric-value">{file.git_churn_score.toFixed(1)}</span>
            </div>
          </div>

          <div className="detail-why">
            <h4 className="detail-why-title">Why this score?</h4>
            <ul className="detail-why-list">
              {reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>

          <p className="detail-note">
            Predicted risk = 35% complexity + 35% churn + 30% test gap. Heuristic estimate only.
          </p>
        </div>

        <div className="detail-divider" />

        {/* ── Phase 7: Verified incident evidence ── */}
        <VerifiedIncidentEvidence file={file} />

        <div className="detail-divider" />

        {/* ── Phase 7: Observed risk ── */}
        {file.observed_risk != null && <ObservedRiskPanel file={file} />}

        <div className="detail-divider" />

        {/* ── AI investigation ── */}
        <div className="detail-ai-block">
          <div className="detail-block-label">Bug Investigation</div>

          {investStatus === 'idle' && (
            <button className="invest-btn" onClick={handleInvestigate}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.4"/>
                <line x1="9.5" y1="9.5" x2="13" y2="13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              Investigate Bug
            </button>
          )}

          {investStatus === 'loading' && (
            <div className="invest-loading">
              <span className="spinner" aria-hidden="true" />
              Analysing code…
            </div>
          )}

          {investStatus === 'error' && (
            <div className="invest-error">
              <span>⚠ {investError}</span>
              <button className="invest-retry" onClick={handleInvestigate}>Retry</button>
            </div>
          )}

          {investStatus === 'done' && investResult && verifyStatus === 'idle' && (
            <InvestigationPanel
              result={investResult}
              onClear={() => { setInvestStatus('idle'); setInvestResult(null); }}
              onVerify={handleVerify}
              verifyStatus={verifyStatus}
            />
          )}

          {investStatus === 'done' && verifyStatus === 'loading' && (
            <div className="invest-loading">
              <span className="spinner" aria-hidden="true" />
              Running verification tests…
            </div>
          )}

          {verifyStatus === 'error' && (
            <div className="invest-error">
              <span>⚠ {verifyError}</span>
              <button className="invest-retry" onClick={handleVerify}>Retry</button>
            </div>
          )}

          {verifyStatus === 'done' && verifyResult && (
            <VerificationPanel
              result={verifyResult}
              file={file}
              investResult={investResult}
              onClear={() => { setVerifyStatus('idle'); setVerifyResult(null); }}
            />
          )}
        </div>

      </div>
    </div>
  );
}
