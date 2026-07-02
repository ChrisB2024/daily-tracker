import { useEffect, useState } from "react";
import { getGoals, getRepTypes, createRep, createReps } from "../api";

export default function RepScheduling() {
  const [goals, setGoals] = useState([]);
  const [selectedGoal, setSelectedGoal] = useState(null);
  const [repTypes, setRepTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [recurring, setRecurring] = useState(false);
  const [repeatDays, setRepeatDays] = useState(7);

  useEffect(() => {
    loadGoals();
  }, []);

  async function loadGoals() {
    try {
      setLoading(true);
      const data = await getGoals();
      setGoals(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGoalChange(goalId) {
    setSelectedGoal(goalId);
    if (goalId) {
      try {
        const data = await getRepTypes(goalId);
        setRepTypes(data);
      } catch (err) {
        alert("Failed to load rep types: " + err.message);
      }
    }
  }

  async function handleCreateRep(e) {
    e.preventDefault();
    const form = e.target;
    const goalId = form.goal_id.value;
    const repTypeId = form.rep_type_id.value;
    const scheduledDate = form.scheduled_date.value;
    const scheduledTime = form.scheduled_time.value;
    const notes = form.notes.value;

    try {
      if (recurring) {
        const repsArray = [];
        for (let i = 0; i < repeatDays; i++) {
          const d = new Date(scheduledDate);
          d.setDate(d.getDate() + i);
          repsArray.push({
            goal_id: goalId,
            rep_type_id: repTypeId,
            scheduled_date: d.toISOString().split("T")[0],
            scheduled_time: scheduledTime,
            notes: notes || null,
          });
        }
        await createReps(repsArray);
        alert(`${repeatDays} reps scheduled!`);
      } else {
        await createRep({
          goal_id: goalId,
          rep_type_id: repTypeId,
          scheduled_date: scheduledDate,
          scheduled_time: scheduledTime,
          notes: notes || null,
        });
        alert("Rep scheduled!");
      }
      form.reset();
      setSelectedGoal(null);
      setRepTypes([]);
      setRecurring(false);
      setRepeatDays(7);
    } catch (err) {
      alert("Failed to schedule rep: " + err.message);
    }
  }

  if (loading) return <div className="loading">Loading...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="scheduling">
      <h2>Schedule a Rep</h2>

      <form onSubmit={handleCreateRep} className="form">
        <div className="form-group">
          <label>Goal</label>
          <select
            name="goal_id"
            value={selectedGoal || ""}
            onChange={(e) => handleGoalChange(e.target.value)}
            required
          >
            <option value="">— Select a goal —</option>
            {goals.map((goal) => (
              <option key={goal.id} value={goal.id}>
                {goal.title}
              </option>
            ))}
          </select>
        </div>

        {selectedGoal && (
          <>
            <div className="form-group">
              <label>Rep Type</label>
              <select name="rep_type_id" required>
                <option value="">— Select a rep type —</option>
                {repTypes.map((repType) => (
                  <option key={repType.id} value={repType.id}>
                    {repType.name} — {repType.criterion}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Date</label>
              <input type="date" name="scheduled_date" required />
            </div>

            <div className="form-group">
              <label>Time</label>
              <input type="time" name="scheduled_time" required />
            </div>

            <div className="form-group">
              <label style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <input
                  type="checkbox"
                  checked={recurring}
                  onChange={(e) => setRecurring(e.target.checked)}
                />
                Repeat daily
              </label>
            </div>

            {recurring && (
              <div className="form-group">
                <label>Number of days</label>
                <input
                  type="number"
                  value={repeatDays}
                  onChange={(e) => setRepeatDays(Math.min(Math.max(parseInt(e.target.value) || 1, 1), 90))}
                  min="1"
                  max="90"
                />
              </div>
            )}

            <div className="form-group">
              <label>Notes (optional)</label>
              <textarea
                name="notes"
                placeholder="e.g., who to contact, what to build..."
              />
            </div>

            <button type="submit" className="btn-primary">
              {recurring ? `Schedule ${repeatDays} Reps` : "Schedule Rep"}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
