export default function ChainsVisualization({ chains }) {
  if (!chains || chains.length === 0) {
    return null;
  }

  return (
    <section className="chains-visualization">
      <h2>Streak Charts (60 Days)</h2>
      <div className="chains-charts">
        {chains.map((chain) => (
          <ChainChart key={chain.rep_type_id} chain={chain} />
        ))}
      </div>
    </section>
  );
}

function ChainChart({ chain }) {
  const width = 240;
  const height = 100;
  const margin = { top: 6, right: 6, bottom: 16, left: 28 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;

  if (!chain.history || chain.history.length === 0) {
    return null;
  }

  const maxChain = Math.max(...chain.history.map((h) => h.chain_count), 1);
  const points = chain.history.map((h, i) => {
    const x = (i / (chain.history.length - 1)) * plotWidth;
    const y = plotHeight - (h.chain_count / maxChain) * plotHeight;
    return { x, y, count: h.chain_count, date: h.date };
  });

  const polylinePoints = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <div className="chain-chart">
      <div className="chain-chart-header">
        <div>
          <h3>{chain.rep_type_name}</h3>
          <p className="chain-chart-goal">{chain.goal_title}</p>
        </div>
        <div className="chain-streak">
          <div className="streak-value">{chain.current_chain}</div>
          <div className="streak-label">Current</div>
        </div>
      </div>

      <svg width={width} height={height} className="chain-plot">
        <defs>
          <linearGradient id={`grad-${chain.rep_type_id}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#4ade80" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#4ade80" stopOpacity="0" />
          </linearGradient>
        </defs>

        <g transform={`translate(${margin.left},${margin.top})`}>
          {/* Grid lines */}
          {[0, 0.5, 1].map((ratio, i) => (
            <line
              key={`grid-${i}`}
              x1={0}
              x2={plotWidth}
              y1={plotHeight * (1 - ratio)}
              y2={plotHeight * (1 - ratio)}
              className="grid-line"
            />
          ))}

          {/* Y axis */}
          <line x1={0} x2={0} y1={0} y2={plotHeight} stroke="#333" strokeWidth="1" />
          <line x1={0} x2={plotWidth} y1={plotHeight} y2={plotHeight} stroke="#333" strokeWidth="1" />

          {/* Y axis label (max value) */}
          <text x={-8} y={-2} className="axis-label" textAnchor="end">
            {maxChain}
          </text>
          <text x={-8} y={plotHeight + 4} className="axis-label" textAnchor="end">
            0
          </text>

          {/* Filled area under line */}
          <polygon
            points={`0,${plotHeight} ${polylinePoints} ${plotWidth},${plotHeight}`}
            fill={`url(#grad-${chain.rep_type_id})`}
          />

          {/* Polyline */}
          <polyline points={polylinePoints} fill="none" stroke="#4ade80" strokeWidth="2" vectorEffect="non-scaling-stroke" />

          {/* Data points */}
          {points.map((p, i) => (
            <g key={i}>
              <circle
                cx={p.x}
                cy={p.y}
                r="2"
                fill={p.count > 0 ? "#4ade80" : "transparent"}
                stroke={p.count > 0 ? "#4ade80" : "#555"}
                strokeWidth="1"
                className="data-point"
              />
              {p.count > 0 && (
                <title>{`${p.date}: ${p.count} day${p.count > 1 ? "s" : ""}`}</title>
              )}
            </g>
          ))}
        </g>
      </svg>
    </div>
  );
}
