import { useEffect, useState } from "react";
import { getSummary, markMissed as markMissedApi } from "../api";
import Nav from "./Nav";
import StatsHeader from "./StatsHeader";
import FirstRepStrip from "./FirstRepStrip";
import TodayReps from "./TodayReps";
import RhythmChart from "./RhythmChart";
import GoalProgressionsVisualization from "./GoalProgressionsVisualization";
import GoalsManagement from "./GoalsManagement";
import RepScheduling from "./RepScheduling";
import Debrief from "./Debrief";
import History from "./History";
import Analytics from "./Analytics";
import WeekView from "./WeekView";
import "../styles/dashboard.css";

export default function Dashboard() {
  const [view, setView] = useState("today");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
                <p className="today">
                  {new Date(data.today_date).toLocaleDateString("en-US", {
                    weekday: "long",
                    month: "long",
                    day: "numeric",
                  })}
                </p>

                <StatsHeader
                  dailyScore={data.daily_score}
                  weekTotal={data.week_total}
                  weeklyPr={data.weekly_pr}
                />

                <FirstRepStrip rate={data.first_rep_rate} />

                <RhythmChart rhythm30day={data.rhythm_30day} />

                <TodayReps goals={data.goals_with_reps} onRepComplete={fetchData} />
              </div>

              {data.goal_progressions.length > 0 && (
                <div className="dashboard-sidebar">
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
    </div>
  );
}
