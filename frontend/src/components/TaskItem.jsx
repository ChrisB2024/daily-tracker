// "09:00:00" → "9:00 AM". Times arrive as plain local wall-clock strings from
// the API, so no Date object (and no timezone conversion) is involved.
function formatTime(value) {
  const [h, m] = value.split(":").map(Number);
  const suffix = h < 12 ? "AM" : "PM";
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${suffix}`;
}

// 90 → "1h30", 45 → "45m", 1440 → "24h"
function formatDuration(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  return m === 0 ? `${h}h` : `${h}h${String(m).padStart(2, "0")}`;
}

export default function TaskItem({ task, onComplete }) {
  const isPending = task.status === "pending";
  const statusIcon =
    task.status === "completed" ? "✓" : task.status === "missed" ? "✗" : "○";

  const when = task.is_all_day
    ? "All day"
    : `${formatTime(task.start_time)}–${formatTime(task.end_time)}`;

  return (
    <li className={`task status-${task.status}`}>
      <button
        className="task-button"
        onClick={onComplete}
        disabled={!isPending}
        title={isPending ? "Check off" : task.status}
      >
        {statusIcon}
      </button>
      <span className="title">{task.title || "(untitled)"}</span>
      <span className="time">
        {when} · {formatDuration(task.duration_minutes)}
      </span>
    </li>
  );
}
