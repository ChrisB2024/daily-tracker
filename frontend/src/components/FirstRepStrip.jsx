export default function FirstRepStrip({ rates }) {
  if (!rates || rates.length === 0) {
    return (
      <section className="first-rep-strip">
        <div className="first-rep-label">First rep before noon</div>
        <p className="empty">No rep type is flagged as a first rep.</p>
      </section>
    );
  }

  return (
    <section className="first-rep-strip">
      <div className="first-rep-label">First rep before noon this week</div>
      {rates.map((r) => {
        // rate === null means nothing was scheduled, which is not the same as 0%.
        const scheduled = r.days_scheduled > 0;
        const percentage = scheduled ? Math.round(r.rate * 100) : 0;
        return (
          <div key={r.goal_id} className="first-rep-goal">
            <div className="first-rep-goal-title">{r.goal_title}</div>
            <div className="first-rep-bar">
              <div
                className="first-rep-fill"
                style={{ width: `${percentage}%` }}
              ></div>
            </div>
            <div className="first-rep-pct">
              {scheduled ? (
                <>
                  {percentage}%{" "}
                  <span className="first-rep-days">
                    {r.days_hit}/{r.days_scheduled} days
                  </span>
                </>
              ) : (
                <span className="first-rep-days">none scheduled</span>
              )}
            </div>
          </div>
        );
      })}
    </section>
  );
}
