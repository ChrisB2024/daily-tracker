export default function Nav({ currentView, onViewChange }) {
  return (
    <nav className="nav">
      <button
        className={`nav-button ${currentView === "today" ? "active" : ""}`}
        onClick={() => onViewChange("today")}
      >
        Today
      </button>
      <button
        className={`nav-button ${currentView === "goals" ? "active" : ""}`}
        onClick={() => onViewChange("goals")}
      >
        Goals
      </button>
      <button
        className={`nav-button ${currentView === "history" ? "active" : ""}`}
        onClick={() => onViewChange("history")}
      >
        History
      </button>
      <button
        className={`nav-button ${currentView === "analytics" ? "active" : ""}`}
        onClick={() => onViewChange("analytics")}
      >
        Analytics
      </button>
      <button
        className={`nav-button ${currentView === "week" ? "active" : ""}`}
        onClick={() => onViewChange("week")}
      >
        Week
      </button>
    </nav>
  );
}
