export default function RepItem({ rep, onComplete, onDelete, calendarEnabled }) {
  const isPending = rep.status === "pending";
  const isCompleted = rep.status === "completed";
  const isMissed = rep.status === "missed";

  const statusIcon = isCompleted ? "✓" : isMissed ? "✗" : "○";

  return (
    <li className={`rep status-${rep.status}`}>
      <button
        className="rep-button"
        onClick={onComplete}
        disabled={!isPending}
        title={!isPending ? `${rep.status}` : "Mark complete"}
      >
        {statusIcon}
      </button>
      <span className="title">[{rep.rep_type_name}]</span>
      <span className="time">{rep.scheduled_time}</span>
      {calendarEnabled && !rep.calendar_event_id && (
        // Muted, never --missed: "missed" means you did not do the rep. This is
        // the system failing to mirror it, which is a different thing.
        <span
          className="rep-unsynced"
          title="Not on the calendar — syncing this rep failed"
        >
          ⚠
        </span>
      )}
      {isPending && (
        <button
          className="rep-delete-button"
          onClick={onDelete}
          title="Delete rep"
        >
          ✕
        </button>
      )}
    </li>
  );
}
