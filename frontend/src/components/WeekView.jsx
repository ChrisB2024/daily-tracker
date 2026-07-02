import { useEffect, useState } from "react";
import { completeRep, deleteRep } from "../api";

function parseISODate(dateString) {
  const [year, month, day] = dateString.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export default function WeekView() {
  const [week, setWeek] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchWeek();
  }, []);

  async function fetchWeek() {
    try {
      setLoading(true);
      const response = await fetch("/summary/week");
      if (!response.ok) throw new Error("Failed to fetch week");
      const data = await response.json();
      setWeek(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCompleteRep(repId) {
    try {
      await completeRep(repId);
      fetchWeek();
    } catch (err) {
      alert("Failed to complete rep: " + err.message);
    }
  }

  async function handleDeleteRep(repId) {
    if (!confirm("Delete this rep? This cannot be undone.")) return;
    try {
      await deleteRep(repId);
      fetchWeek();
    } catch (err) {
      alert("Failed to delete rep: " + err.message);
    }
  }

  if (loading) return <div className="loading">Loading week...</div>;
  if (error) return <div className="error">Error: {error}</div>;
  if (!week) return <div className="empty">No data.</div>;

  return (
    <div className="week-view">
      <h2>
        Week of {parseISODate(week.week_start).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
      </h2>

      <div className="week-grid">
        {week.days.map((day) => (
          <div key={day.date} className="day-card">
            <div className="day-header">
              <div className="day-name">{day.day_name}</div>
              <div className="day-date">
                {parseISODate(day.date).toLocaleDateString("en-US", { month: "numeric", day: "numeric" })}
              </div>
            </div>

            <div className="day-content">
              {day.goals_with_reps.length === 0 ? (
                <p className="empty">No reps scheduled</p>
              ) : (
                day.goals_with_reps.map((goal) => (
                  <div key={goal.goal_id} className="goal-group">
                    <h4>{goal.goal_title}</h4>
                    {goal.reps.length > 0 ? (
                      <ul className="reps">
                        {goal.reps.map((rep) => (
                          <li key={rep.rep_id} className={`rep status-${rep.status}`}>
                            <button
                              className="rep-button"
                              onClick={() => handleCompleteRep(rep.rep_id)}
                              disabled={rep.status !== "pending"}
                              title={rep.status !== "pending" ? rep.status : "Mark complete"}
                            >
                              {rep.status === "completed" ? "✓" : rep.status === "missed" ? "✗" : "○"}
                            </button>
                            <span className="title">[{rep.rep_type_name}]</span>
                            <span className="time">{rep.scheduled_time}</span>
                            <button
                              className="rep-delete-button"
                              onClick={() => handleDeleteRep(rep.rep_id)}
                              title="Delete rep"
                            >
                              ✕
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="empty">No reps for this goal</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
