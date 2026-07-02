export default function StatsHeader({ dailyScore, weekTotal, weeklyPr }) {
  return (
    <section className="stats">
      <div className="stat">
        <div className="stat-label">Today</div>
        <div className="stat-value">{dailyScore}</div>
      </div>
      <div className="stat">
        <div className="stat-label">This Week</div>
        <div className="stat-value">{weekTotal}</div>
      </div>
      <div className="stat">
        <div className="stat-label">PR</div>
        <div className="stat-value">{weeklyPr}</div>
      </div>
    </section>
  );
}
