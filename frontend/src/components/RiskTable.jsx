function levelClass(level) {
  return { High: 'badge--high', Medium: 'badge--medium', Low: 'badge--low' }[level] ?? '';
}

function ColdZoneBadge() {
  return (
    <span
      className="badge badge--cold"
      title="Cold Zone — predicted risk without verified incident evidence"
    >
      ❄ Cold Zone
    </span>
  );
}

export default function RiskTable({ files, selected, onSelect }) {
  return (
    <div className="table-wrapper">
      <table className="risk-table">
        <thead>
          <tr>
            <th>File</th>
            <th title="Normalised cyclomatic complexity (0–100)">Complexity</th>
            <th title="Number of git commits that touched this file">Churn</th>
            <th title="Test coverage percentage">Coverage</th>
            <th title="Phase 1 heuristic risk score (0–100) — unchanged">Predicted Risk</th>
            <th title="Verified incidents from Verified Memory only">Verified</th>
            <th title="Observed risk after adding incident evidence">Observed Risk</th>
            <th>Level</th>
          </tr>
        </thead>
        <tbody>
          {files.map((f) => {
            const isSelected = selected?.file === f.file;
            const hasIncidents = (f.verified_incident_count ?? 0) > 0;
            const isCold = f.is_cold_zone === true;
            const observedRisk = f.observed_risk ?? f.risk_score;
            const observedLevel = f.observed_risk_level ?? f.risk_level;
            return (
              <tr
                key={f.file}
                className={`table-row ${isSelected ? 'table-row--selected' : ''} ${isCold ? 'table-row--cold' : ''}`}
                onClick={() => onSelect(isSelected ? null : f)}
                title="Click to see details"
              >
                <td className="cell-file">
                  {f.file}
                  {isCold && <ColdZoneBadge />}
                </td>
                <td className="cell-num">{f.complexity_score.toFixed(1)}</td>
                <td className="cell-num">{f.git_churn_commits}</td>
                <td className="cell-num">{f.test_coverage_pct.toFixed(0)}%</td>
                <td className="cell-num cell-score">
                  <span
                    className="score-pill"
                    style={{ '--pct': `${f.risk_score}%` }}
                    title="Phase 1 predicted risk — heuristic estimate only"
                  >
                    {f.risk_score.toFixed(1)}
                  </span>
                </td>
                <td className="cell-num">
                  {hasIncidents ? (
                    <span className="incident-count" title="Verified incidents from Verified Memory">
                      {f.verified_incident_count} ✓
                    </span>
                  ) : (
                    <span className="incident-none" title="No verified incident evidence yet">—</span>
                  )}
                </td>
                <td className="cell-num cell-score">
                  <span
                    className="score-pill"
                    style={{ '--pct': `${observedRisk}%` }}
                    title={`Observed risk = predicted (${f.risk_score.toFixed(1)}) + incident contribution (${(f.incident_score ?? 0).toFixed(1)})`}
                  >
                    {observedRisk.toFixed(1)}
                  </span>
                </td>
                <td>
                  <span className={`badge ${levelClass(observedLevel)}`}>
                    {observedLevel}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="table-hint">Click a row to inspect file details. ❄ = Cold Zone (predicted risk, no verified incidents yet).</p>
    </div>
  );
}
