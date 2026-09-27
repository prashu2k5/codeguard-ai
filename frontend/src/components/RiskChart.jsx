const COLORS = { High: '#ef4444', Medium: '#f59e0b', Low: '#22c55e' };
const COLD_COLOR = '#7dd3fc';

export default function RiskChart({ files }) {
  const sorted = [...files].sort((a, b) => (b.observed_risk ?? b.risk_score) - (a.observed_risk ?? a.risk_score));

  return (
    <div className="chart">
      <div className="chart-legend">
        <div className="chart-legend-item">
          <span className="chart-legend-dot" style={{ background: '#94a3b8' }} />
          <span>Predicted Risk</span>
        </div>
        <div className="chart-legend-item">
          <span className="chart-legend-dot" style={{ background: '#7c3aed' }} />
          <span>Observed Risk (+ incident evidence)</span>
        </div>
        <div className="chart-legend-item">
          <span className="chart-legend-dot" style={{ background: COLD_COLOR }} />
          <span>❄ Cold Zone</span>
        </div>
      </div>

      {sorted.map((f) => {
        const predictedColor = COLORS[f.risk_level] ?? '#94a3b8';
        const observedLevel  = f.observed_risk_level ?? f.risk_level;
        const observedColor  = f.is_cold_zone ? COLD_COLOR : (COLORS[observedLevel] ?? '#94a3b8');
        const predicted = Math.max(2, f.risk_score);
        const observed  = Math.max(2, f.observed_risk ?? f.risk_score);
        const hasIncidents = (f.verified_incident_count ?? 0) > 0;
        const incDelta = (f.observed_risk ?? f.risk_score) - f.risk_score;

        return (
          <div key={f.file} className="chart-row">
            <span className="chart-label" title={f.file}>
              {f.is_cold_zone && <span className="chart-cold-icon">❄ </span>}
              {f.file}
            </span>
            <div className="chart-bars">
              {/* Predicted risk bar */}
              <div className="chart-bar-track" title={`Predicted risk: ${f.risk_score.toFixed(1)}`}>
                <div
                  className="chart-bar-fill chart-bar-predicted"
                  style={{ width: `${predicted}%`, backgroundColor: predictedColor }}
                />
              </div>
              {/* Observed risk bar — only if different */}
              {hasIncidents && (
                <div className="chart-bar-track chart-bar-track--observed"
                  title={`Observed risk: ${(f.observed_risk ?? f.risk_score).toFixed(1)} (+${incDelta.toFixed(1)} from ${f.verified_incident_count} incident${f.verified_incident_count !== 1 ? 's' : ''})`}>
                  <div
                    className="chart-bar-fill chart-bar-observed"
                    style={{ width: `${observed}%`, backgroundColor: '#7c3aed55' }}
                  />
                  <div
                    className="chart-bar-fill chart-bar-delta"
                    style={{
                      width: `${Math.max(0, observed - predicted)}%`,
                      left: `${predicted}%`,
                      backgroundColor: '#7c3aed',
                    }}
                  />
                </div>
              )}
            </div>
            <div className="chart-scores">
              <span className="chart-score" style={{ color: predictedColor }}>{f.risk_score.toFixed(1)}</span>
              {hasIncidents && (
                <span className="chart-score-observed" style={{ color: '#7c3aed' }}>
                  → {(f.observed_risk ?? f.risk_score).toFixed(1)}
                </span>
              )}
            </div>
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
