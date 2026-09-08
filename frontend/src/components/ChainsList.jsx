import { useState } from "react";

function ChainRow({ chain }) {
  return (
    <li className="chain">
      <div className="chain-header">
        <strong>{chain.rep_type_name}</strong>
        <span className="chain-goal">{chain.goal_title}</span>
      </div>
      <div className="chain-value">
        {chain.current_chain} {chain.current_chain === 1 ? "day" : "days"}
      </div>
      {chain.last_completed_date ? (
        <div className="chain-last">
          Last:{" "}
          {new Date(
            chain.last_completed_date + "T00:00:00"
          ).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
        </div>
      ) : (
        <div className="chain-last">Never completed</div>
      )}
    </li>
  );
}

export default function ChainsList({ chains }) {
  const [showZero, setShowZero] = useState(false);

  if (!chains || chains.length === 0) {
    return (
      <section>
        <h2>Chains</h2>
        <p className="empty">No active rep types yet.</p>
      </section>
    );
  }

  // Only live chains lead. The rest stay one click away — the count is always
  // visible, so nothing is hidden, but a daily glance is not swamped by rep
  // types that have never been used.
  const alive = chains
    .filter((c) => c.current_chain > 0)
    .sort((a, b) => b.current_chain - a.current_chain);
  const zero = chains.filter((c) => c.current_chain === 0);
  const never = zero.filter((c) => c.last_completed_date === null).length;

  return (
    <section>
      <h2>Chains</h2>

      {alive.length > 0 ? (
        <ul className="chains">
          {alive.map((chain) => (
            <ChainRow key={chain.rep_type_id} chain={chain} />
          ))}
        </ul>
      ) : (
        <p className="empty">No chain is currently running.</p>
      )}

      {zero.length > 0 && (
        <>
          <button
            className="chains-toggle"
            onClick={() => setShowZero(!showZero)}
            aria-expanded={showZero}
          >
            {showZero ? "▾" : "▸"} {zero.length} at zero
            {never > 0 && ` · ${never} never completed`}
          </button>
          {showZero && (
            <ul className="chains chains-zero">
              {zero.map((chain) => (
                <ChainRow key={chain.rep_type_id} chain={chain} />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
