import { useEffect, useState } from "react";
import {
  getGoals,
  createGoal,
  updateGoal,
  deleteGoal,
  deleteGoalHard,
  getRepTypes,
  createRepType,
  updateRepType,
  deleteRepType,
} from "../api";

export default function GoalsManagement({ onBack }) {
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showNewGoalForm, setShowNewGoalForm] = useState(false);
  const [expandedGoal, setExpandedGoal] = useState(null);
  const [repTypes, setRepTypes] = useState({});
  const [formError, setFormError] = useState(null);
  const [editingGoalId, setEditingGoalId] = useState(null);
  const [goalEditForm, setGoalEditForm] = useState({});
  const [editingRepTypeId, setEditingRepTypeId] = useState(null);
  const [repTypeEditForm, setRepTypeEditForm] = useState({});
  const [showArchived, setShowArchived] = useState(false);

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

  async function loadRepTypes(goalId) {
    if (repTypes[goalId]) return;
    try {
      const data = await getRepTypes(goalId);
      setRepTypes((prev) => ({ ...prev, [goalId]: data }));
    } catch (err) {
      alert("Failed to load rep types: " + err.message);
    }
  }

  async function handleCreateGoal(e) {
    e.preventDefault();
    const form = e.target;
    const title = form.title.value;
    const description = form.description.value;
    const targetDate = form.target_date.value;

    try {
      setFormError(null);
      await createGoal({
        title,
        description: description || null,
        target_date: targetDate || null,
      });
      setShowNewGoalForm(false);
      form.reset();
      loadGoals();
    } catch (err) {
      setFormError(err.message);
    }
  }

  async function handleArchiveGoal(goalId) {
    if (!confirm("Archive this goal? (Data will be preserved)")) return;
    try {
      await deleteGoal(goalId);
      loadGoals();
    } catch (err) {
      alert("Failed to archive goal: " + err.message);
    }
  }

  async function handlePermanentlyDeleteGoal(goalId) {
    if (
      !confirm(
        "⚠️ PERMANENTLY DELETE this goal and all its reps? This cannot be undone."
      )
    ) {
      return;
    }
    try {
      await deleteGoalHard(goalId);
      loadGoals();
    } catch (err) {
      alert("Failed to delete goal: " + err.message);
    }
  }

  function startEditGoal(goal) {
    setEditingGoalId(goal.id);
    setGoalEditForm({
      title: goal.title,
      description: goal.description || "",
      target_date: goal.target_date || "",
      status: goal.status || "active",
    });
  }

  async function saveGoal(goalId) {
    try {
      await updateGoal(goalId, goalEditForm);
      setEditingGoalId(null);
      loadGoals();
    } catch (err) {
      alert("Failed to update goal: " + err.message);
    }
  }

  function cancelEditGoal() {
    setEditingGoalId(null);
    setGoalEditForm({});
  }

  function startEditRepType(repType) {
    setEditingRepTypeId(repType.id);
    setRepTypeEditForm({
      name: repType.name,
      criterion: repType.criterion,
      duration_minutes: repType.duration_minutes,
      daily_floor: repType.daily_floor ?? null,
      weekly_target: repType.weekly_target ?? null,
      is_first_rep: repType.is_first_rep || false,
    });
  }

  async function saveRepType(repTypeId, goalId) {
    try {
      const data = { ...repTypeEditForm };
      // Convert empty strings to null for optional fields
      if (data.criterion === "") data.criterion = null;
      await updateRepType(repTypeId, data);
      setEditingRepTypeId(null);
      delete repTypes[goalId];
      loadRepTypes(goalId);
    } catch (err) {
      alert("Failed to update rep type: " + err.message);
    }
  }

  function cancelEditRepType() {
    setEditingRepTypeId(null);
    setRepTypeEditForm({});
  }


  async function handleCreateRepType(goalId, e) {
    e.preventDefault();
    const form = e.currentTarget;
    const name = form.name.value;
    const criterion = form.criterion.value;
    const duration = parseInt(form.duration_minutes.value);

    try {
      await createRepType(goalId, {
        name,
        criterion,
        duration_minutes: duration,
      });
      form.reset();
      delete repTypes[goalId];
      loadRepTypes(goalId);
    } catch (err) {
      alert("Failed to create rep type: " + err.message);
    }
  }

  async function handleDeleteRepType(repTypeId, goalId) {
    if (!confirm("Archive this rep type?")) return;
    try {
      await deleteRepType(repTypeId);
      delete repTypes[goalId];
      loadRepTypes(goalId);
    } catch (err) {
      alert("Failed to delete rep type: " + err.message);
    }
  }

  if (loading) return <div className="loading">Loading goals...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="management">
      <h2>Goals & Rep Types</h2>

      {showNewGoalForm && (
        <form onSubmit={handleCreateGoal} className="form">
          <h3>New Goal</h3>
          {formError && <div className="form-error">{formError}</div>}
          <input
            type="text"
            name="title"
            placeholder="Goal title"
            required
            autoFocus
          />
          <textarea
            name="description"
            placeholder="Description (optional)"
          />
          <input
            type="date"
            name="target_date"
            placeholder="Target date (optional)"
          />
          <div className="form-buttons">
            <button type="submit">Create Goal</button>
            <button
              type="button"
              onClick={() => {
                setShowNewGoalForm(false);
                setFormError(null);
              }}
              className="cancel"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {!showNewGoalForm && (
        <div style={{ display: "flex", gap: "1rem", marginBottom: "1.5rem" }}>
          <button onClick={() => setShowNewGoalForm(true)} className="btn-primary">
            + New Goal
          </button>
          <button
            onClick={() => setShowArchived(!showArchived)}
            className="btn-secondary"
          >
            {showArchived ? "Hide" : "Show"} Archived
          </button>
        </div>
      )}

      <ul className="goals-list">
        {goals
          .filter((goal) => showArchived || goal.status !== "archived")
          .map((goal) => (
          <li key={goal.id} className="goal-card">
            <div className="goal-header">
              {editingGoalId === goal.id ? (
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <input
                    type="text"
                    value={goalEditForm.title}
                    onChange={(e) => setGoalEditForm({ ...goalEditForm, title: e.target.value })}
                    placeholder="Goal title"
                    style={{ padding: "0.5rem" }}
                  />
                  <textarea
                    value={goalEditForm.description}
                    onChange={(e) => setGoalEditForm({ ...goalEditForm, description: e.target.value })}
                    placeholder="Description"
                    style={{ padding: "0.5rem" }}
                  />
                  <input
                    type="date"
                    value={goalEditForm.target_date}
                    onChange={(e) => setGoalEditForm({ ...goalEditForm, target_date: e.target.value })}
                    style={{ padding: "0.5rem" }}
                  />
                  <select
                    value={goalEditForm.status}
                    onChange={(e) => setGoalEditForm({ ...goalEditForm, status: e.target.value })}
                    style={{ padding: "0.5rem" }}
                  >
                    <option value="active">Active</option>
                    <option value="paused">Paused</option>
                    <option value="completed">Completed</option>
                    <option value="archived">Archived</option>
                  </select>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      onClick={() => saveGoal(goal.id)}
                      className="btn-primary"
                      style={{ fontSize: "0.9rem", padding: "0.4rem 0.8rem" }}
                    >
                      Save
                    </button>
                    <button
                      onClick={cancelEditGoal}
                      className="btn-secondary"
                      style={{ fontSize: "0.9rem", padding: "0.4rem 0.8rem" }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div>
                    <h3>{goal.title}</h3>
                    {goal.description && <p className="goal-desc">{goal.description}</p>}
                    {goal.target_date && (
                      <p className="goal-date">Target: {goal.target_date}</p>
                    )}
                    {goal.status !== "active" && (
                      <p className="goal-date" style={{ color: "#888" }}>Status: {goal.status}</p>
                    )}
                  </div>
                  <div className="goal-actions">
                    <button
                      onClick={() => startEditGoal(goal)}
                      className="btn-secondary"
                      title="Edit goal"
                    >
                      ✎
                    </button>
                    <button
                      onClick={() => {
                        setExpandedGoal(expandedGoal === goal.id ? null : goal.id);
                        loadRepTypes(goal.id);
                      }}
                      className="btn-secondary"
                    >
                      {expandedGoal === goal.id ? "Hide" : "Show"} Reps
                    </button>
                    <button
                      onClick={() => handleArchiveGoal(goal.id)}
                      className="btn-danger"
                      title="Archive (data preserved)"
                    >
                      Archive
                    </button>
                    <button
                      onClick={() => handlePermanentlyDeleteGoal(goal.id)}
                      className="btn-danger-hard"
                      title="Permanently delete"
                    >
                      ✕ Delete
                    </button>
                  </div>
                </>
              )}
            </div>

            {expandedGoal === goal.id && (
              <div className="goal-reps">
                <h4>Rep Types</h4>
                {repTypes[goal.id]?.length > 0 ? (
                  <ul className="rep-types-list">
                    {repTypes[goal.id].map((repType) => (
                      <li key={repType.id} className="rep-type-item">
                        {editingRepTypeId === repType.id ? (
                          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                            <input
                              type="text"
                              value={repTypeEditForm.name}
                              onChange={(e) => setRepTypeEditForm({ ...repTypeEditForm, name: e.target.value })}
                              placeholder="Rep type name"
                              style={{ padding: "0.4rem" }}
                            />
                            <input
                              type="text"
                              value={repTypeEditForm.criterion || ""}
                              onChange={(e) => setRepTypeEditForm({ ...repTypeEditForm, criterion: e.target.value === "" ? null : e.target.value })}
                              placeholder="Criterion"
                              style={{ padding: "0.4rem" }}
                            />
                            <input
                              type="number"
                              value={repTypeEditForm.duration_minutes}
                              onChange={(e) => setRepTypeEditForm({ ...repTypeEditForm, duration_minutes: parseInt(e.target.value) })}
                              placeholder="Duration (min)"
                              min="15"
                              max="90"
                              style={{ padding: "0.4rem" }}
                            />
                            <input
                              type="number"
                              value={repTypeEditForm.daily_floor}
                              onChange={(e) => setRepTypeEditForm({ ...repTypeEditForm, daily_floor: e.target.value === "" ? null : parseInt(e.target.value) })}
                              placeholder="Daily floor (optional)"
                              style={{ padding: "0.4rem" }}
                            />
                            <input
                              type="number"
                              value={repTypeEditForm.weekly_target}
                              onChange={(e) => setRepTypeEditForm({ ...repTypeEditForm, weekly_target: e.target.value === "" ? null : parseInt(e.target.value) })}
                              placeholder="Weekly target (optional)"
                              style={{ padding: "0.4rem" }}
                            />
                            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                              <input
                                type="checkbox"
                                checked={repTypeEditForm.is_first_rep}
                                onChange={(e) => setRepTypeEditForm({ ...repTypeEditForm, is_first_rep: e.target.checked })}
                              />
                              First rep (before noon)
                            </label>
                            <div style={{ display: "flex", gap: "0.5rem" }}>
                              <button
                                onClick={() => saveRepType(repType.id, goal.id)}
                                className="btn-primary"
                                style={{ fontSize: "0.85rem", padding: "0.3rem 0.6rem" }}
                              >
                                Save
                              </button>
                              <button
                                onClick={cancelEditRepType}
                                className="btn-secondary"
                                style={{ fontSize: "0.85rem", padding: "0.3rem 0.6rem" }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div>
                              <strong>{repType.name}</strong>
                              <p className="criterion">{repType.criterion}</p>
                              <p className="duration">{repType.duration_minutes} min</p>
                              {repType.daily_floor && <p className="duration">Daily: {repType.daily_floor}</p>}
                              {repType.weekly_target && <p className="duration">Weekly: {repType.weekly_target}</p>}
                              {repType.is_first_rep && <p className="duration" style={{ color: "#4ade80" }}>★ First rep</p>}
                            </div>
                            <div style={{ display: "flex", gap: "0.25rem" }}>
                              <button
                                onClick={() => startEditRepType(repType)}
                                className="btn-secondary"
                                title="Edit rep type"
                                style={{ padding: "0.25rem 0.5rem", fontSize: "0.9rem" }}
                              >
                                ✎
                              </button>
                              <button
                                onClick={() =>
                                  handleDeleteRepType(repType.id, goal.id)
                                }
                                className="btn-danger-small"
                              >
                                ×
                              </button>
                            </div>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty">No rep types yet.</p>
                )}

                <form onSubmit={(e) => handleCreateRepType(goal.id, e)} className="rep-type-form">
                  <h4>New Rep Type</h4>
                  <input
                    type="text"
                    name="name"
                    placeholder="Rep type name (e.g., Outbound rep)"
                    required
                  />
                  <input
                    type="text"
                    name="criterion"
                    placeholder="Done/not-done criterion (one line)"
                    required
                  />
                  <input
                    type="number"
                    name="duration_minutes"
                    placeholder="Duration (minutes)"
                    min="15"
                    max="90"
                    required
                  />
                  <button type="submit">Add Rep Type</button>
                </form>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
