import { useEffect, useState } from "react";
import {
  getGoals,
  createGoal,
  updateGoal,
  deleteGoal,
  deleteGoalHard,
  getGoalRelations,
  createGoalRelation,
  deleteGoalRelation,
} from "../api";
import PushSettings from "./PushSettings";

// Goals only. Rep types were managed here until Unit 20 of the calendar-first
// redesign; tasks now tag straight to a goal by its title, so each card shows
// the [Title] to use on the calendar.

export default function GoalsManagement({ onBack }) {
  const [goals, setGoals] = useState([]);
  const [relations, setRelations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showNewGoalForm, setShowNewGoalForm] = useState(false);
  const [formError, setFormError] = useState(null);
  const [editingGoalId, setEditingGoalId] = useState(null);
  const [goalEditForm, setGoalEditForm] = useState({});
  const [showArchived, setShowArchived] = useState(false);

  useEffect(() => {
    loadGoals();
  }, []);

  async function loadGoals() {
    try {
      setLoading(true);
      const [data, rels] = await Promise.all([getGoals(), getGoalRelations()]);
      setGoals(data);
      setRelations(rels);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
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

  if (loading) return <div className="loading">Loading goals...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="management">
      <PushSettings />

      <h2>Goals</h2>

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
                    <p className="goal-tag" title="Start a calendar event with this to tag it">
                      [{goal.title}]
                    </p>
                    <RelatedGoals
                      goal={goal}
                      goals={goals}
                      relations={relations}
                      onChange={loadGoals}
                    />
                    {goal.description && <p className="goal-desc">{goal.description}</p>}
                    {goal.target_date && (
                      <p className="goal-date">Target: {goal.target_date}</p>
                    )}
                    {goal.status !== "active" && (
                      <p className="goal-date" style={{ color: "var(--muted)" }}>Status: {goal.status}</p>
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

          </li>
        ))}
      </ul>
    </div>
  );
}

// Which goals this one is related to (Unit 26). The graph draws a line between
// related goals' hubs — only because Chris said so here, never inferred.
function RelatedGoals({ goal, goals, relations, onChange }) {
  const byId = Object.fromEntries(goals.map((g) => [g.id, g]));
  const mine = relations
    .filter((r) => r.goal_a_id === goal.id || r.goal_b_id === goal.id)
    .map((r) => ({ id: r.id, other: byId[r.goal_a_id === goal.id ? r.goal_b_id : r.goal_a_id] }))
    .filter((r) => r.other);
  const taken = new Set(mine.map((r) => r.other.id));
  const candidates = goals.filter(
    (g) => g.id !== goal.id && g.status !== "archived" && !taken.has(g.id),
  );

  async function add(otherId) {
    if (!otherId) return;
    try {
      await createGoalRelation(goal.id, otherId);
      onChange();
    } catch (err) {
      alert("Failed: " + err.message);
    }
  }

  async function remove(relationId) {
    try {
      await deleteGoalRelation(relationId);
      onChange();
    } catch (err) {
      alert("Failed: " + err.message);
    }
  }

  return (
    <div className="related-goals">
      <span className="related-label">Related:</span>
      {mine.length === 0 && <span className="related-none">none</span>}
      {mine.map((r) => (
        <span key={r.id} className="related-chip">
          {r.other.title}
          <button
            className="related-remove"
            onClick={() => remove(r.id)}
            title={`Not related to ${r.other.title}`}
            aria-label={`Remove relation to ${r.other.title}`}
          >
            ×
          </button>
        </span>
      ))}
      {candidates.length > 0 && (
        <select
          className="related-add"
          value=""
          onChange={(e) => add(e.target.value)}
          aria-label={`Relate ${goal.title} to another goal`}
        >
          <option value="">+ related goal…</option>
          {candidates.map((g) => (
            <option key={g.id} value={g.id}>
              {g.title}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
