export default function ChainsVisualization({ chains }) {
  if (!chains || chains.length === 0) {
    return null;
  }

  // Live chains only. Production carries 53 rep types and 46 of them sit at
  // zero — that many 240x100 charts is not a sidebar, and a wall of flat lines
  // is not information.
  const alive = chains
    .filter((c) => c.current_chain > 0)
    .sort((a, b) => b.current_chain - a.current_chain);

  return (
    <section className="chains-visualization">
      <h2>Streak Charts (60 Days)</h2>
      {alive.length > 0 ? (
        <div className="chains-charts">
          {alive.map((chain) => (
            <ChainChart key={chain.rep_type_id} chain={chain} />
          ))}
        </div>
      ) : (
        <p className="empty">No chain is currently running.</p>
      )}
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
            <stop offset="0%" stopColor="var(--completed)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="var(--completed)" stopOpacity="0" />
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
          <line x1={0} x2={0} y1={0} y2={plotHeight} stroke="var(--border)" strokeWidth="1" />
          <line x1={0} x2={plotWidth} y1={plotHeight} y2={plotHeight} stroke="var(--border)" strokeWidth="1" />

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
          <polyline points={polylinePoints} fill="none" stroke="var(--completed)" strokeWidth="2" vectorEffect="non-scaling-stroke" />

          {/* Data points */}
          {points.map((p, i) => (
            <g key={i}>
              <circle
                cx={p.x}
                cy={p.y}
                r="2"
                fill={p.count > 0 ? "var(--completed)" : "transparent"}
                stroke={p.count > 0 ? "var(--completed)" : "var(--pending)"}
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
