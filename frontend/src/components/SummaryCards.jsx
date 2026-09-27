function Card({ label, value, variant }) {
  return (
    <div className={`card card--${variant}`}>
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
      <Card label="Average Risk" value={`${counts.avgRisk}`} variant={avgColor} />
      <Card label="High Risk" value={counts.high} variant="high" />
      <Card label="Medium Risk" value={counts.medium} variant="medium" />
      <Card label="Low Risk" value={counts.low} variant="low" />
    </div>
  );
}
