function Card({ label, value, variant, title }) {
  return (
    <div className={`card card--${variant}`} title={title}>
      <span className="card-value">{value}</span>
      <span className="card-label">{label}</span>
    </div>
  );
}

export default function SummaryCards({ counts }) {
  const avgColor =
    counts.avgRisk >= 66 ? 'high' : counts.avgRisk >= 33 ? 'medium' : 'low';

  return (
    <div className="cards-row">
      <Card label="Files Scanned" value={counts.total} variant="neutral" />
      <Card
        label="Average Risk"
        value={`${counts.avgRisk}`}
        variant={avgColor}
        title="Heuristic estimate — not a prediction of failures"
      />
      <Card label="High Risk" value={counts.high} variant="high" />
      <Card label="Medium Risk" value={counts.medium} variant="medium" />
      <Card label="Low Risk" value={counts.low} variant="low" />
      {counts.coldZones != null && (
        <Card
          label="Cold Zones"
          value={counts.coldZones}
          variant={counts.coldZones > 0 ? 'medium' : 'neutral'}
          title="Predicted risk with zero verified incident evidence — needs investigation"
        />
      )}
      {counts.verifiedIncidents != null && (
        <Card
          label="Verified Incidents"
          value={counts.verifiedIncidents}
          variant={counts.verifiedIncidents > 0 ? 'high' : 'neutral'}
          title="Total verified incidents across all files (from Verified Memory only)"
        />
      )}
    </div>
  );
}
