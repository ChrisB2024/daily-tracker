import { useEffect, useState } from "react";
import { getHistory } from "../api";

export default function History() {
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  async function fetchHistory() {
    try {
      setLoading(true);
      const data = await getHistory();
      setGoals(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="loading">Loading history...</div>;
  if (error) return <div className="error">Error: {error}</div>;
  if (goals.length === 0) return <div className="empty">No goals yet.</div>;

  return (
    <div className="history">
      <h2>Goal History</h2>
      <div className="history-charts">
        {goals.map((goal) => (
          <GoalHistoryChart key={goal.goal_id} goal={goal} />
        ))}
      </div>
    </div>
  );
}

function GoalHistoryChart({ goal }) {
  if (!goal.progression || goal.progression.length === 0) {
    return null;
  }

  const viewBoxWidth = 1200;
  const viewBoxHeight = 200;
  const margin = { top: 20, right: 20, bottom: 40, left: 40 };
  const plotWidth = viewBoxWidth - margin.left - margin.right;
  const plotHeight = viewBoxHeight - margin.top - margin.bottom;

  const minValue = Math.min(...goal.progression.map((p) => p.cumulative_count), 0);
  const maxValue = Math.max(...goal.progression.map((p) => p.cumulative_count), 1);
  const range = maxValue - minValue || 1;
  const centerY = plotHeight * (maxValue / range);

  const points = goal.progression.map((p, i) => {
    const x = (i / (goal.progression.length - 1)) * plotWidth;
    const normalized = (p.cumulative_count - minValue) / range;
    const y = plotHeight - normalized * plotHeight;
    const parsedDate = parseISODate(p.date);
    return { x, y, count: p.cumulative_count, date: p.date, parsedDate };
  });

  const polylinePoints = points.map((p) => `${p.x},${p.y}`).join(" ");
  const isPositive = (count) => count >= 0;

  // Calculate month boundaries for X axis labels
  const firstDate = parseISODate(goal.progression[0].date);
  const lastDate = parseISODate(goal.progression[goal.progression.length - 1].date);
  const monthLabels = getMonthLabels(firstDate, lastDate, goal.progression);

  return (
    <div className="history-chart">
      <h3>{goal.goal_title}</h3>
      <p className="history-date-range">
        {firstDate.toLocaleDateString("en-US", {
          year: "numeric",
          month: "short",
          day: "numeric",
        })}{" "}
        —{" "}
        {lastDate.toLocaleDateString("en-US", {
          year: "numeric",
          month: "short",
          day: "numeric",
        })}
      </p>

      <svg viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`} className="history-plot">
        <defs>
          <linearGradient id={`hist-grad-${goal.goal_id}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#4ade80" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#4ade80" stopOpacity="0" />
          </linearGradient>
        </defs>

        <g transform={`translate(${margin.left},${margin.top})`}>
          {/* Month grid lines and labels */}
          {monthLabels.map((label, i) => (
            <g key={i}>
              <line
                x1={label.x}
                x2={label.x}
                y1={0}
                y2={plotHeight}
                stroke="#333"
                strokeWidth="1"
                opacity="0.3"
              />
              <text x={label.x} y={plotHeight + 20} textAnchor="middle" className="axis-label" fontSize="12">
                {label.text}
              </text>
            </g>
          ))}

          {/* Center line at 0 */}
          <line
            x1={0}
            x2={plotWidth}
            y1={centerY}
            y2={centerY}
            stroke="#555"
            strokeWidth="1"
            strokeDasharray="2"
          />

          {/* Y axis */}
          <line x1={0} x2={0} y1={0} y2={plotHeight} stroke="#333" strokeWidth="1" />
          <line x1={0} x2={plotWidth} y1={plotHeight} y2={plotHeight} stroke="#333" strokeWidth="1" />

          {/* Y axis labels */}
          <text x={-8} y={-4} className="axis-label" textAnchor="end" fontSize="12">
            {Math.round(maxValue)}
          </text>
          <text x={-8} y={plotHeight + 4} className="axis-label" textAnchor="end" fontSize="12">
            {Math.round(minValue)}
          </text>

          {/* Filled area under line */}
          <polygon
            points={`0,${centerY} ${polylinePoints} ${plotWidth},${centerY}`}
            fill={`url(#hist-grad-${goal.goal_id})`}
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
              <title>{`${p.parsedDate.toLocaleDateString("en-US")}: ${p.count}`}</title>
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}

function parseISODate(dateString) {
  const [year, month, day] = dateString.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function getMonthLabels(startDate, endDate, progression) {
  const labels = [];
  const totalDays = progression.length;

  // Generate month boundaries
  let current = new Date(startDate);
  while (current <= endDate) {
    const firstOfMonth = new Date(current.getFullYear(), current.getMonth(), 1);
    if (firstOfMonth >= startDate && firstOfMonth <= endDate) {
      const daysFromStart = Math.floor(
        (firstOfMonth - startDate) / (1000 * 60 * 60 * 24)
      );
      const x = (daysFromStart / (totalDays - 1)) * (1200 - 60);
      labels.push({
        x,
        text: firstOfMonth.toLocaleDateString("en-US", { month: "short" }),
      });
    }
    current.setMonth(current.getMonth() + 1);
  }

  return labels;
}
