import { lazy, Suspense, useEffect, useState } from "react";

// "2026-09-07" through new Date() is parsed as UTC midnight and then rendered in
// local time, which shows the previous day anywhere west of Greenwich. Same
// helper as WeekView, History and Debrief.
function parseISODate(dateString) {
  const [year, month, day] = dateString.split("-").map(Number);
  return new Date(year, month - 1, day);
}
import { getSummary } from "../api";
import Nav from "./Nav";
import TodayTasks from "./TodayTasks";
import GoalsManagement from "./GoalsManagement";
import History from "./History";
import Analytics from "./Analytics";
import WeekView from "./WeekView";
import "../styles/dashboard.css";

// three.js is large; load the graph only when a day is opened.
const TaskGraph = lazy(() => import("./TaskGraph"));

export default function Dashboard() {
  const [view, setView] = useState("today");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // The day open in the graph view. Not in Nav: a day is reached by clicking it.
  const [graphDate, setGraphDate] = useState(null);

  function openDayGraph(isoDate) {
    setGraphDate(isoDate);
    setView("day-graph");
  }

  // Today needs only the server's date (settings.tz) from /summary now that the
  // rep widgets are gone (Unit 20). Refetched each time Today is opened, so the
  // date rolls over at midnight; the previous date stays up until it arrives.
  useEffect(() => {
    if (view !== "today") return;
    getSummary()
      .then((summary) => {
        setData(summary);
        setError(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [view]);

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Daily Tracker</h1>
      </header>

      <Nav currentView={view} onViewChange={setView} />

      {view === "today" && (
        <>
          {loading && <div className="loading">Loading...</div>}
          {error && <div className="error">Error: {error}</div>}
          {!loading && !error && data && (
            <div className="dashboard-grid">
              <div className="dashboard-main">
                <button
                  className="today today-link"
                  onClick={() => openDayGraph(data.today_date)}
                  title="Open this day's graph"
                >
                  {parseISODate(data.today_date).toLocaleDateString("en-US", {
                    weekday: "long",
                    month: "long",
                    day: "numeric",
                  })}{" "}
                  <span className="today-link-hint">· day graph →</span>
                </button>

                <TodayTasks />
              </div>
            </div>
          )}
        </>
      )}

      {view === "goals" && <GoalsManagement />}

      {view === "history" && <History />}

      {view === "analytics" && <Analytics />}

      {view === "week" && <WeekView />}

      {view === "day-graph" && graphDate && (
        <Suspense fallback={<div className="loading">Loading…</div>}>
          <TaskGraph initialDate={graphDate} onBack={() => setView("today")} />
        </Suspense>
      )}
    </div>
  );
}
