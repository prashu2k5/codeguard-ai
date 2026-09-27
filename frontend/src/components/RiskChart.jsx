const COLORS = { High: '#ef4444', Medium: '#f59e0b', Low: '#22c55e' };

export default function RiskChart({ files }) {
  const sorted = [...files].sort((a, b) => b.risk_score - a.risk_score);

  return (
    <div className="chart">
      {sorted.map((f) => {
        const color = COLORS[f.risk_level] ?? '#94a3b8';
        const pct = Math.max(2, f.risk_score); // minimum visible bar width
        return (
          <div key={f.file} className="chart-row">
            <span className="chart-label" title={f.file}>
              {f.file}
            </span>
            <div className="chart-bar-track">
              <div
                className="chart-bar-fill"
                style={{ width: `${pct}%`, backgroundColor: color }}
              />
            </div>
            <span className="chart-score">{f.risk_score.toFixed(1)}</span>
          </div>
        );
      })}
      <div className="chart-axis">
        <span>0</span>
        <span>25</span>
        <span>50</span>
        <span>75</span>
        <span>100</span>
      </div>
    </div>
  );
}
