export default function GoalProgressionsVisualization({ goalProgressions }) {
  if (!goalProgressions || goalProgressions.length === 0) {
    return null;
  }

  return (
    <section className="goal-progressions">
      <h2>Goal Progression (60 Days)</h2>
      <div className="progressions-charts">
        {goalProgressions.map((goal) => (
          <GoalProgressionChart key={goal.goal_id} goal={goal} />
        ))}
      </div>
    </section>
  );
}

function GoalProgressionChart({ goal }) {
  const width = 240;
  const height = 100;
  const margin = { top: 6, right: 6, bottom: 16, left: 28 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;

  if (!goal.progression || goal.progression.length === 0) {
    return null;
  }

  const minValue = Math.min(...goal.progression.map((p) => p.cumulative_count), 0);
  const maxValue = Math.max(...goal.progression.map((p) => p.cumulative_count), 1);
  const range = maxValue - minValue || 1;
  const centerY = plotHeight * (maxValue / range);

  const points = goal.progression.map((p, i) => {
    const x = (i / (goal.progression.length - 1)) * plotWidth;
    const normalized = (p.cumulative_count - minValue) / range;
    const y = plotHeight - normalized * plotHeight;
    return { x, y, count: p.cumulative_count, date: p.date };
  });

  const polylinePoints = points.map((p) => `${p.x},${p.y}`).join(" ");
  const isPositive = (count) => count >= 0;

  return (
    <div className="progression-chart">
      <div className="progression-chart-header">
        <div>
          <h3>{goal.goal_title}</h3>
        </div>
        <div className="progression-value">
          <div className="value">{goal.progression[goal.progression.length - 1]?.cumulative_count || 0}</div>
          <div className="label">Current</div>
        </div>
      </div>

      <svg width={width} height={height} className="progression-plot">
        <defs>
          <linearGradient id={`prog-grad-${goal.goal_id}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#4ade80" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#4ade80" stopOpacity="0" />
          </linearGradient>
        </defs>

        <g transform={`translate(${margin.left},${margin.top})`}>
          {/* Center line at 0 */}
          <line
            x1={0}
            x2={plotWidth}
            y1={centerY}
            y2={centerY}
            stroke="#555"
            strokeWidth="0.5"
            strokeDasharray="2"
          />

          {/* Y axis */}
          <line x1={0} x2={0} y1={0} y2={plotHeight} stroke="#333" strokeWidth="1" />
          <line x1={0} x2={plotWidth} y1={plotHeight} y2={plotHeight} stroke="#333" strokeWidth="1" />

          {/* Y axis labels */}
          <text x={-8} y={-2} className="axis-label" textAnchor="end">
            {Math.round(maxValue)}
          </text>
          <text x={-8} y={plotHeight + 4} className="axis-label" textAnchor="end">
            {Math.round(minValue)}
          </text>

          {/* Filled area under line */}
          <polygon
            points={`0,${centerY} ${polylinePoints} ${plotWidth},${centerY}`}
            fill={`url(#prog-grad-${goal.goal_id})`}
          />

          {/* Polyline */}
          <polyline
            points={polylinePoints}
            fill="none"
            stroke="#4ade80"
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />

          {/* Data points */}
          {points.map((p, i) => (
            <g key={i}>
              <circle
                cx={p.x}
                cy={p.y}
                r="2"
                fill={isPositive(p.count) ? "#4ade80" : "#ef4444"}
                stroke={isPositive(p.count) ? "#4ade80" : "#ef4444"}
                strokeWidth="1"
                className="data-point"
              />
              <title>{`${p.date}: ${p.count}`}</title>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}
