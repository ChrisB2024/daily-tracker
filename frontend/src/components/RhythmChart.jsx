export default function RhythmChart({ rhythm30day }) {
  if (!rhythm30day || Object.keys(rhythm30day).length === 0) {
    return <div className="rhythm-empty">No data yet</div>;
  }

  const maxCount = Math.max(...Object.values(rhythm30day), 1);

  // Get current month/year
  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth();

  const monthYear = today.toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });

  // Get last day of current month
  const lastDay = new Date(year, month + 1, 0).getDate();
  const firstDate = new Date(year, month, 1);
  const firstDayOfWeek = firstDate.getDay();

  // Build weeks grid
  const weeks = [];
  let currentWeek = [];

  // Pad start of first week
  for (let i = 0; i < firstDayOfWeek; i++) {
    currentWeek.push(null);
  }

  // Add days 1 to lastDay
  for (let day = 1; day <= lastDay; day++) {
    if (currentWeek.length === 7) {
      weeks.push(currentWeek);
      currentWeek = [];
    }
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const dayOfWeek = new Date(year, month, day).getDay();
    const dayName = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"][dayOfWeek];
    currentWeek.push({ day, dateStr, dayName });
  }

  // Pad end of last week
  while (currentWeek.length > 0 && currentWeek.length < 7) {
    currentWeek.push(null);
  }
  if (currentWeek.length > 0) {
    weeks.push(currentWeek);
  }

  const getColor = (count) => {
    if (count === 0) return "#222";
    const intensity = count / maxCount;
    if (intensity < 0.33) return "#4ade80";
    if (intensity < 0.66) return "#22c55e";
    return "#16a34a";
  };

  return (
    <section className="rhythm-chart">
      <h2>{monthYear}</h2>
      <div className="rhythm-grid">
        {weeks.map((week, weekIdx) => (
          <div key={weekIdx} className="rhythm-week">
            {week.map((item, dayIdx) => {
              if (!item) {
                return (
                  <div key={`empty-${dayIdx}`} className="rhythm-day empty">
                  </div>
                );
              }
              const { day, dateStr, dayName } = item;
              const count = rhythm30day[dateStr] || 0;
              return (
                <div
                  key={dateStr}
                  className="rhythm-day"
                  style={{
                    backgroundColor: getColor(count),
                  }}
                  title={`${dateStr}: ${count} reps`}
                >
                  <span className="rhythm-day-label">
                    {dayName} {day}
                  </span>
                  <span className="rhythm-day-count">{count}</span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div className="rhythm-legend">
        <span>Less</span>
        <div className="legend-bar">
          <div style={{ backgroundColor: "#222" }}></div>
          <div style={{ backgroundColor: "#4ade80" }}></div>
          <div style={{ backgroundColor: "#22c55e" }}></div>
          <div style={{ backgroundColor: "#16a34a" }}></div>
        </div>
        <span>More</span>
      </div>
    </section>
  );
}
