import { useEffect, useState } from "react";
import { completeTask, getTasks, giveCancelReason, syncTasks } from "../api";
import TaskItem from "./TaskItem";

// Sync first, then fetch — but a failed sync still fetches what is saved, so
// the list is never blocked on Google. Returns data only; the component sets
// state from it, which keeps setState out of the effect body.
async function syncThenFetch() {
  const outcome = { synced: null, syncError: null, tasks: null, error: null };
  try {
    outcome.synced = await syncTasks();
  } catch (err) {
    outcome.syncError = err.message;
  }
  try {
    outcome.tasks = await getTasks();
  } catch (err) {
    outcome.error = err.message;
  }
  return outcome;
}

// Today's tasks: events on Google Calendar titled "[Goal] …", grouped by goal.
// Opening the section syncs once, so it shows the calendar as it is now rather
// than as of the last 15-minute background sync; the button syncs again.
export default function TodayTasks() {
  const [tasks, setTasks] = useState(null);
  const [error, setError] = useState(null);
  const [syncing, setSyncing] = useState(true);
  const [syncedAt, setSyncedAt] = useState(null);
  const [syncError, setSyncError] = useState(null);
  const [unmatched, setUnmatched] = useState([]);

  async function load() {
    try {
      setTasks(await getTasks());
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }

  function apply(outcome) {
    if (outcome.synced) {
      setSyncedAt(new Date(outcome.synced.synced_at));
      setUnmatched(outcome.synced.unmatched);
    }
    setSyncError(outcome.syncError);
    setTasks(outcome.tasks);
    setError(outcome.error);
    setSyncing(false);
  }

  useEffect(() => {
    syncThenFetch().then(apply);
  }, []);

  function handleSync() {
    setSyncing(true);
    syncThenFetch().then(apply);
  }

  async function handleComplete(taskId) {
    try {
      await completeTask(taskId);
      await load();
    } catch (err) {
      alert("Failed: " + err.message);
    }
  }

  const header = (
    <div className="tasks-header">
      <h2>Today's Tasks</h2>
      <div className="tasks-sync">
        {syncedAt && (
          <span className="tasks-synced-at">
            Synced{" "}
            {syncedAt.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
          </span>
        )}
        <button className="tasks-sync-button" onClick={handleSync} disabled={syncing}>
          {syncing ? "Syncing…" : "Sync"}
        </button>
      </div>
    </div>
  );

  if (tasks === null && !error) {
    return (
      <section className="tasks-section">
        {header}
        <div className="loading">Loading…</div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="tasks-section">
        {header}
        <div className="error">Error: {error}</div>
      </section>
    );
  }

  const active = tasks.filter((t) => t.status !== "cancelled");
  const removed = tasks.filter((t) => t.status === "cancelled");

  // Group by goal, keeping the API's order (all-day first, then by time).
  const groups = [];
  for (const task of active) {
    let group = groups.find((g) => g.goalId === task.goal_id);
    if (!group) {
      group = { goalId: task.goal_id, goalTitle: task.goal_title, tasks: [] };
      groups.push(group);
    }
    group.tasks.push(task);
  }

  return (
    <section className="tasks-section">
      {header}

      {syncError && (
        <p className="tasks-note">{syncError} — showing the last saved tasks.</p>
      )}
      {unmatched.length > 0 && (
        <p className="tasks-note">
          No goal matches {unmatched.map((tag) => `[${tag}]`).join(", ")}. Check the
          spelling on the calendar.
        </p>
      )}

      {groups.length === 0 ? (
        <p className="empty">
          No tasks today. Add an event to Google Calendar titled [Goal name] what you
          are doing.
        </p>
      ) : (
        groups.map((group) => (
          <div key={group.goalId} className="goal-group">
            <h3>{group.goalTitle}</h3>
            <ul className="tasks">
              {group.tasks.map((task) => (
                <TaskItem
                  key={task.id}
                  task={task}
                  onComplete={() => handleComplete(task.id)}
                />
              ))}
            </ul>
          </div>
        ))
      )}

      {removed.length > 0 && <RemovedTasks tasks={removed} onSaved={load} />}
    </section>
  );
}

// Tasks whose calendar event was deleted. Each asks for one line of why, until
// midnight; after that the question is dropped (decided 2026-09-24).
function RemovedTasks({ tasks, onSaved }) {
  return (
    <div className="goal-group removed-tasks">
      <h3>Removed today — why?</h3>
      <ul className="tasks">
        {tasks.map((task) => (
          <RemovedTask key={task.id} task={task} onSaved={onSaved} />
        ))}
      </ul>
    </div>
  );
}

function RemovedTask({ task, onSaved }) {
  const [reason, setReason] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      await giveCancelReason(task.id, reason);
      onSaved();
    } catch (err) {
      alert("Failed: " + err.message);
    }
  }

  return (
    <li className="task status-cancelled">
      <span className="title">
        {task.title || "(untitled)"} <span className="removed-goal">· {task.goal_title}</span>
      </span>
      {task.cancel_reason ? (
        <span className="removed-reason">{task.cancel_reason}</span>
      ) : (
        <form className="removed-form" onSubmit={handleSubmit}>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={200}
            placeholder="One line — anyone with the app's link can read it"
            aria-label={`Why was ${task.title} removed?`}
          />
          <button type="submit" disabled={reason.trim() === ""}>
            Save
          </button>
        </form>
      )}
    </li>
  );
}
