function levelClass(level) {
  return { High: 'badge--high', Medium: 'badge--medium', Low: 'badge--low' }[level] ?? '';
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
            <th title="Weighted risk score (0–100)">Risk Score</th>
            <th>Level</th>
          </tr>
        </thead>
        <tbody>
          {files.map((f) => {
            const isSelected = selected?.file === f.file;
            return (
              <tr
                key={f.file}
                className={`table-row ${isSelected ? 'table-row--selected' : ''}`}
                onClick={() => onSelect(isSelected ? null : f)}
                title="Click to see details"
              >
                <td className="cell-file">{f.file}</td>
                <td className="cell-num">{f.complexity_score.toFixed(1)}</td>
                <td className="cell-num">{f.git_churn_commits}</td>
                <td className="cell-num">{f.test_coverage_pct.toFixed(0)}%</td>
                <td className="cell-num cell-score">
                  <span className="score-pill"
                    style={{ '--pct': `${f.risk_score}%` }}>
                    {f.risk_score.toFixed(1)}
                  </span>
                </td>
                <td>
                  <span className={`badge ${levelClass(f.risk_level)}`}>
                    {f.risk_level}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="table-hint">Click a row to inspect file details.</p>
    </div>
  );
}
