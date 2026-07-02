export default function ChainsList({ chains }) {
  return (
    <section>
      <h2>Chains</h2>
      <ul className="chains">
        {chains.map((chain) => (
          <li key={chain.rep_type_id} className="chain">
            <div className="chain-header">
              <strong>{chain.rep_type_name}</strong>
              <span className="chain-goal">{chain.goal_title}</span>
            </div>
            <div className="chain-value">{chain.current_chain} days</div>
            {chain.last_completed_date && (
              <div className="chain-last">
                Last:{" "}
                {new Date(chain.last_completed_date).toLocaleDateString(
                  "en-US",
                  { month: "short", day: "numeric" }
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
