const STEPS = [
  {
    num: '1',
    icon: '🔍',
    title: 'Scan',
    color: '#2563eb',
    description: 'Scan the codebase to get a heuristic risk estimate for every file.',
    detail: 'Each file gets a predicted risk score (0–100) based on cyclomatic complexity, git churn, and test coverage gap.',
    action: 'Click "Scan Repository" on the Dashboard.',
  },
  {
    num: '2',
    icon: '🐛',
    title: 'Investigate',
    color: '#7c3aed',
    description: 'Click a high-risk or Cold Zone file to investigate the likely bug.',
    detail: 'The system analyses the source code and identifies a root cause and a candidate fix — without claiming it is verified.',
    action: 'Click any file row → click "Investigate Bug".',
  },
  {
    num: '3',
    icon: '✅',
    title: 'Verify',
    color: '#059669',
    description: 'Independently verify the fix using a three-stage automated test gate.',
    detail: 'Stage 1: the bug is reproduced (FAIL). Stage 2: the fix is applied (PASS). Stage 3: the full regression suite still passes.',
    action: 'Click "Verify Fix" after investigating.',
  },
  {
    num: '4',
    icon: '💾',
    title: 'Remember',
    color: '#d97706',
    description: 'Save the independently verified incident to Verified Memory.',
    detail: 'Only incidents where all three verification stages passed are saved. Verification result = PASS is the sole eligibility gate.',
    action: 'Click "Save to Verified Memory" in the verification panel.',
  },
  {
    num: '5',
    icon: '♻',
    title: 'Reuse + Recheck',
    color: '#dc2626',
    description: 'When a similar bug appears, past knowledge surfaces — with a re-verify warning.',
    detail: 'Memory context is shown during future investigations. The stored fix is offered as a candidate, but always requires fresh independent verification.',
    action: 'Investigate a similar file — past incident will appear as context.',
  },
];

const FLOW_STEPS = [
  'Codebase',
  'Risk Scan',
  'Cold Zone / High Risk',
  'Bug Investigation',
  'Fix Candidate',
  'Independent Verification',
  'Verified Fix',
  'Save to Memory',
  'Future Bug',
  'Memory Match',
  'Reuse Candidate',
  'Fresh Verification',
  'Updated Risk Evidence',
];

export default function DemoGuide({ onStartDemo }) {
  return (
    <div className="guide-page">
      <div className="guide-header">
        <h2 className="guide-title">CodeGuard AI — Demo Guide</h2>
        <p className="guide-subtitle">
          A transparent, evidence-based approach to code quality: find risk, verify fixes, remember knowledge.
        </p>
        <button className="guide-start-btn" onClick={onStartDemo}>
          → Go to Dashboard
        </button>
      </div>

      {/* ── Core principle ── */}
      <div className="guide-principle">
        <p>
          <strong>Core principle:</strong> Risk is estimated from code signals.
          Fixes are only trusted after independent automated test verification.
          Verified knowledge is stored and reused — with mandatory re-verification for new code.
        </p>
      </div>

      {/* ── End-to-end flow ── */}
      <div className="guide-section">
        <h3 className="guide-section-title">End-to-End Workflow</h3>
        <div className="guide-flow">
          {FLOW_STEPS.map((step, i) => (
            <div key={step} className="guide-flow-step">
              <div className="guide-flow-node">{step}</div>
              {i < FLOW_STEPS.length - 1 && <div className="guide-flow-arrow">↓</div>}
            </div>
          ))}
        </div>
      </div>

      {/* ── 5 major steps ── */}
      <div className="guide-section">
        <h3 className="guide-section-title">5 Major Steps</h3>
        <div className="guide-steps">
          {STEPS.map(s => (
            <div key={s.num} className="guide-step">
              <div className="guide-step-num" style={{ background: s.color }}>{s.num}</div>
              <div className="guide-step-body">
                <div className="guide-step-header">
                  <span className="guide-step-icon">{s.icon}</span>
                  <span className="guide-step-title">{s.title}</span>
                </div>
                <p className="guide-step-description">{s.description}</p>
                <p className="guide-step-detail">{s.detail}</p>
                <p className="guide-step-action"><strong>How:</strong> {s.action}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Key safety points ── */}
      <div className="guide-section">
        <h3 className="guide-section-title">Safety Principles</h3>
        <div className="guide-safety-grid">
          {[
            ['Predicted risk ≠ proof of a bug', 'Risk scores are heuristic estimates from code signals. They do not prove a bug exists.'],
            ['Verification gate is strict', 'A fix is only "verified" when: bug reproduced → fix passes → regression suite passes.'],
            ['Memory ≠ automatic truth', 'Stored incidents are evidence. They require fresh independent verification when reused.'],
            ['Phase 1 score never changed', 'The original risk_score is never silently modified. Phase 7 adds observed_risk separately.'],
            ['No AI fabrication', 'If the AI is unavailable, the system falls back to deterministic heuristics — never invents data.'],
            ['No external APIs needed', 'The full demo workflow runs locally with no internet connection or API key.'],
          ].map(([title, text]) => (
            <div key={title} className="guide-safety-card">
              <div className="guide-safety-title">✓ {title}</div>
              <p className="guide-safety-text">{text}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Risk formula ── */}
      <div className="guide-section">
        <h3 className="guide-section-title">Transparent Risk Formula</h3>
        <pre className="guide-formula">
{`Phase 1 (predicted risk):
  risk_score = 0.35 × complexity_score
             + 0.35 × churn_score
             + 0.30 × (100 − coverage_pct)
  — clamped to [0, 100]

Phase 7 (observed risk after verified incidents):
  incident_score = min(30, verified_incident_count × 10)
  observed_risk  = min(100, risk_score + incident_score)

Cold Zone:  risk_score ≥ 35  AND  verified_incident_count = 0  AND  not yet investigated`}
        </pre>
      </div>

      <button className="guide-start-btn guide-start-btn--bottom" onClick={onStartDemo}>
        → Start Demo — Go to Dashboard
      </button>
    </div>
  );
}
