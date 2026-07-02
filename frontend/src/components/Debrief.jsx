import { useEffect, useState } from "react";
import { getDebrief } from "../api";

function parseISODate(dateString) {
  const [year, month, day] = dateString.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export default function Debrief() {
  const [debrief, setDebrief] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audio] = useState(new Audio());

  useEffect(() => {
    fetchDebrief();
  }, []);

  async function fetchDebrief() {
    try {
      setLoading(true);
      const data = await getDebrief();
      setDebrief(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handlePlayAudio() {
    if (!debrief?.audio_base64) {
      alert("Audio not available");
      return;
    }

    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
      return;
    }

    try {
      const audioBlob = new Blob(
        [Uint8Array.from(atob(debrief.audio_base64), (c) => c.charCodeAt(0))],
        { type: "audio/mpeg" }
      );
      const audioUrl = URL.createObjectURL(audioBlob);
      audio.src = audioUrl;
      audio.onended = () => setIsPlaying(false);
      audio.play();
      setIsPlaying(true);
    } catch (err) {
      alert("Failed to play audio: " + err.message);
    }
  }

  function downloadAudio() {
    if (!debrief?.audio_base64) return;

    const audioBlob = new Blob(
      [Uint8Array.from(atob(debrief.audio_base64), (c) => c.charCodeAt(0))],
      { type: "audio/mpeg" }
    );
    const url = URL.createObjectURL(audioBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `debrief-${debrief.week_start}.mp3`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="debrief">
      <header className="debrief-header">
        <h1>Weekly Debrief</h1>
        {debrief && (
          <p className="debrief-week">
            {parseISODate(debrief.week_start).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })}{" "}
            −{" "}
            {parseISODate(debrief.week_end).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })}
          </p>
        )}
      </header>

      {loading && <div className="loading">Generating debrief...</div>}
      {error && <div className="error">Error: {error}</div>}

      {!loading && !error && debrief && (
        <div className="debrief-content">
          {/* Stats */}
          <div className="debrief-stats">
            <div className="stat-box">
              <div className="stat-value">{debrief.stats.completed}</div>
              <div className="stat-label">Completed</div>
            </div>
            <div className="stat-box">
              <div className="stat-value">{debrief.stats.missed}</div>
              <div className="stat-label">Missed</div>
            </div>
            <div className="stat-box">
              <div className="stat-value">{debrief.stats.completion_rate}%</div>
              <div className="stat-label">Rate</div>
            </div>
          </div>

          {/* Summary */}
          <div className="debrief-section">
            <h2>Your Week</h2>
            <p className="debrief-summary">{debrief.summary}</p>
          </div>

          {/* Audio Player */}
          {debrief.audio_base64 && (
            <div className="debrief-audio">
              <button
                className="btn-play"
                onClick={handlePlayAudio}
                title={isPlaying ? "Pause" : "Play"}
              >
                {isPlaying ? "⏸" : "▶"}
              </button>
              <button className="btn-download" onClick={downloadAudio} title="Download">
                ⬇
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
