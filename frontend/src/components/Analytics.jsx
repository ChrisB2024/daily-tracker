import { useEffect, useState } from "react";
import { getAnalytics } from "../api";

export default function Analytics() {
  const [analytics, setAnalytics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  async function fetchAnalytics() {
    try {
      setLoading(true);
      const data = await getAnalytics();
      setAnalytics(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="loading">Loading analytics...</div>;
  if (error) return <div className="error">Error: {error}</div>;
  if (analytics.length === 0) return <div className="empty">No rep data yet.</div>;

  const totalCompleted = analytics.reduce((sum, a) => sum + a.completed_count, 0);
  const totalReps = analytics.reduce((sum, a) => sum + a.total_reps, 0);
  const overallPct = totalReps > 0 ? Math.round((totalCompleted / totalReps) * 100) : 0;

  return (
    <div className="analytics">
      <h2>Rep Type Analytics</h2>

      <div className="analytics-summary">
        <div className="summary-stat">
          <div className="stat-label">Overall Completion</div>
          <div className="stat-value">{overallPct}%</div>
          <div className="stat-detail">{totalCompleted} of {totalReps} reps</div>
        </div>
      </div>

      <div className="analytics-table">
        <div className="table-header">
          <div className="col-name">Rep Type</div>
          <div className="col-goal">Goal</div>
          <div className="col-stats">Stats</div>
          <div className="col-completion">Completion</div>
        </div>

        {analytics.map((rep) => (
          <div key={rep.rep_type_id} className="table-row">
            <div className="col-name">
              <strong>{rep.rep_type_name}</strong>
            </div>
            <div className="col-goal">
              <span className="goal-title">{rep.goal_title}</span>
            </div>
            <div className="col-stats">
              <span className="stat-item completed">{rep.completed_count} done</span>
              <span className="stat-item missed">{rep.missed_count} missed</span>
              <span className="stat-item pending">{rep.pending_count} pending</span>
              <span className="stat-item total">({rep.total_reps} total)</span>
            </div>
            <div className="col-completion">
              <div className="completion-bar">
                <div
                  className="completion-fill"
                  style={{ width: `${rep.completion_pct}%` }}
                ></div>
              </div>
              <span className="completion-text">{rep.completion_pct}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
