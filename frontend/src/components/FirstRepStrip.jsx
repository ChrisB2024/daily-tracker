export default function FirstRepStrip({ rate }) {
  const percentage = Math.round(rate * 100);

  return (
    <section className="first-rep-strip">
      <div className="first-rep-label">First rep before noon this week</div>
      <div className="first-rep-bar">
        <div
          className="first-rep-fill"
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
      <div className="first-rep-pct">{percentage}%</div>
    </section>
  );
}
