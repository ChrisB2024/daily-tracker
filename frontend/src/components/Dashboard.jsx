import { lazy, Suspense, useEffect, useState } from "react";

// "2026-09-07" through new Date() is parsed as UTC midnight and then rendered in
// local time, which shows the previous day anywhere west of Greenwich. Same
// helper as WeekView, History and Debrief.
function parseISODate(dateString) {
  const [year, month, day] = dateString.split("-").map(Number);
  return new Date(year, month - 1, day);
}
import { getSummary, markMissed as markMissedApi } from "../api";
import Nav from "./Nav";
import StatsHeader from "./StatsHeader";
import FirstRepStrip from "./FirstRepStrip";
import ChainsList from "./ChainsList";
import ChainsVisualization from "./ChainsVisualization";
import TodayReps from "./TodayReps";
import TodayTasks from "./TodayTasks";
import RhythmChart from "./RhythmChart";
import GoalProgressionsVisualization from "./GoalProgressionsVisualization";
import GoalsManagement from "./GoalsManagement";
import RepScheduling from "./RepScheduling";
import Debrief from "./Debrief";
import History from "./History";
import Analytics from "./Analytics";
import WeekView from "./WeekView";
import "../styles/dashboard.css";

// three.js is large; load the graph only when a day is opened.
const DayGraph = lazy(() => import("./DayGraph"));

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

  useEffect(() => {
    if (view === "today") {
      fetchData();
    }
  }, [view]);

  async function fetchData() {
    try {
      setLoading(true);
      const summary = await getSummary();
      setData(summary);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleMarkMissed() {
    try {
      await markMissedApi();
      fetchData();
      alert("Marked missed reps as red in calendar");
    } catch (err) {
      alert("Failed: " + err.message);
    }
  }

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

                <StatsHeader
                  dailyScore={data.daily_score}
                  weekTotal={data.week_total}
                  weeklyPr={data.weekly_pr}
                />

                <FirstRepStrip rates={data.first_rep_rates} />

                <ChainsList chains={data.chains} />

                <RhythmChart rhythm30day={data.rhythm_30day} />

                <TodayReps
                  goals={data.goals_with_reps}
                  onRepComplete={fetchData}
                  calendarEnabled={data.calendar_enabled}
                />
              </div>

              {(data.chains.some((c) => c.current_chain > 0) ||
                data.goal_progressions.length > 0) && (
                <div className="dashboard-sidebar">
                  <ChainsVisualization chains={data.chains} />
                  <GoalProgressionsVisualization goalProgressions={data.goal_progressions} />
                </div>
              )}

              <footer className="dashboard-footer">
                <button onClick={handleMarkMissed}>Run end-of-day sweep</button>
              </footer>
            </div>
          )}
        </>
      )}

      {view === "goals" && <GoalsManagement />}

      {view === "schedule" && <RepScheduling />}

      {view === "debrief" && <Debrief />}

      {view === "history" && <History />}

      {view === "analytics" && <Analytics />}

      {view === "week" && <WeekView />}

      {view === "day-graph" && graphDate && (
        <Suspense fallback={<div className="loading">Loading…</div>}>
          <DayGraph initialDate={graphDate} onBack={() => setView("today")} />
        </Suspense>
      )}
    </div>
  );
}
