export default function RepItem({ rep, onComplete, onDelete }) {
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
      <button
        className="rep-delete-button"
        onClick={onDelete}
        title="Delete rep"
      >
        ✕
      </button>
    </li>
  );
}
