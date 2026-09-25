import { useEffect, useRef, useState } from "react";
import ForceGraph3D from "3d-force-graph";
import SpriteText from "three-spritetext";
import * as THREE from "three";
import { getTaskGraph } from "../api";

// The points-and-lines graph of tasks and goals, for one day (Unit 18) or one
// Mon–Sun week (Unit 19). Lazy-loaded from Dashboard: three.js is large, and
// Today should not pay for it.

// "2026-09-24" ± n days, done on the calendar date alone so no timezone can
// shift it (same reason as parseISODate in Dashboard).
function shiftDate(iso, days) {
  const [y, m, d] = iso.split("-").map(Number);
  const next = new Date(y, m - 1, d + days);
  const pad = (n) => String(n).padStart(2, "0");
  return `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
}

// Monday of the week containing `iso` — the same Mon–Sun week the API uses.
function mondayOf(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const weekday = new Date(y, m - 1, d).getDay(); // 0 = Sunday
  return shiftDate(iso, -((weekday + 6) % 7));
}

function formatWeek(mondayIso) {
  const fmt = (iso) => {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };
  return `Week of ${fmt(mondayIso)} – ${fmt(shiftDate(mondayIso, 6))}`;
}

function formatLongDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

// 90 → "1h30", 45 → "45m", 0 → "0m"
function formatMinutes(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  return m === 0 ? `${h}h` : `${h}h${String(m).padStart(2, "0")}`;
}

// WebGL cannot read CSS variables, so the tokens are read once from :root.
// dashboard.css stays the only place a colour is defined.
function readTokens() {
  const css = getComputedStyle(document.documentElement);
  const token = (name) => css.getPropertyValue(name).trim();
  return {
    bg: token("--bg"),
    pending: token("--pending"),
    muted: token("--muted"),
    missed: token("--missed"),
    goals: [1, 2, 3, 4, 5, 6].map((i) => token(`--goal-${i}`)),
  };
}

const NODE_REL_SIZE = 3;

// Radius 3d-force-graph gives a node of value v: cbrt(v) * nodeRelSize.
function nodeValue(n) {
  // Goals are hubs sized by time completed; tasks by their own length.
  return n.kind === "goal" ? 4 + n.minutes_completed / 15 : 1 + n.duration_minutes / 30;
}

function nodeRadius(n) {
  return Math.cbrt(nodeValue(n)) * NODE_REL_SIZE;
}

// One soft radial gradient, shared by every halo. Drawn with additive blending,
// it only ever adds light, so the background stays black. (A bloom
// post-processing pass was tried first and washed the whole canvas grey.)
let haloTexture = null;
function getHaloTexture() {
  if (haloTexture) return haloTexture;
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,0.9)");
  g.addColorStop(0.25, "rgba(255,255,255,0.35)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  haloTexture = new THREE.CanvasTexture(canvas);
  return haloTexture;
}

function makeHalo(color, radius, strength) {
  const halo = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: getHaloTexture(),
      color,
      transparent: true,
      opacity: strength,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  halo.scale.setScalar(radius * 5);
  return halo;
}

export default function TaskGraph({ initialDate, initialMode = "day", onBack }) {
  const [mode, setMode] = useState(initialMode); // "day" | "week"
  const [date, setDate] = useState(initialDate); // the day shown, or a day in the week shown
  const [result, setResult] = useState({ key: null, data: null, error: null });
  const containerRef = useRef(null);

  const monday = mondayOf(date);
  const key = mode === "day" ? `day:${date}` : `week:${monday}`;

  useEffect(() => {
    const request = mode === "day" ? getTaskGraph({ date }) : getTaskGraph({ weekStart: monday });
    request
      .then((data) => setResult({ key, data, error: null }))
      .catch((err) => setResult({ key, data: null, error: err.message }));
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps -- key encodes mode, date and monday

  const loading = result.key !== key;
  const data = loading ? null : result.data;
  const goals = data ? data.nodes.filter((n) => n.kind === "goal") : [];

  // Build the 3D scene whenever a day's data arrives; tear it down on change.
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !data || data.nodes.length === 0) return;

    const tokens = readTokens();
    // color_slot is fixed per goal by the API, so a goal has the same colour
    // in every day and week view.
    const goalColor = {};
    data.nodes
      .filter((n) => n.kind === "goal")
      .forEach((g) => {
        goalColor[g.goal_id] = tokens.goals[g.color_slot - 1];
      });

    const colorOf = (node) => {
      if (node.kind === "goal" || node.status === "completed") return goalColor[node.goal_id];
      return node.status === "missed" ? tokens.missed : tokens.pending;
    };

    const graph = new ForceGraph3D(el)
      .backgroundColor(tokens.bg)
      .width(el.clientWidth)
      .height(el.clientHeight)
      .showNavInfo(false)
      .nodeVal(nodeValue)
      .nodeRelSize(NODE_REL_SIZE)
      .nodeResolution(16)
      .nodeOpacity(0.95)
      .nodeColor(colorOf)
      .nodeLabel((n) =>
        n.kind === "goal"
          ? `${n.label} — ${formatMinutes(n.minutes_completed)} of ${formatMinutes(n.minutes_planned)} done`
          : `${n.label} · ${formatMinutes(n.duration_minutes)} · ${n.status}`,
      )
      // Every node keeps its sphere and gains a halo; goals also get a label.
      // A missed task replaces its sphere with a hollow wireframe — still
      // visible, never hidden. Pending tasks get no glow: not done yet.
      .nodeThreeObjectExtend((n) => !(n.kind === "task" && n.status === "missed"))
      .nodeThreeObject((n) => {
        const group = new THREE.Group();
        const radius = nodeRadius(n);
        if (n.kind === "task" && n.status === "missed") {
          group.add(
            new THREE.Mesh(
              new THREE.SphereGeometry(radius, 8, 6),
              new THREE.MeshBasicMaterial({ color: tokens.missed, wireframe: true }),
            ),
          );
          group.add(makeHalo(tokens.missed, radius, 0.5));
          return group;
        }
        if (n.kind === "goal" || n.status === "completed") {
          group.add(makeHalo(colorOf(n), radius, n.kind === "goal" ? 0.9 : 0.7));
        }
        if (n.kind === "goal") {
          const label = new SpriteText(
            `${n.label.toUpperCase()}  ${n.task_count} task${n.task_count === 1 ? "" : "s"} · ${formatMinutes(n.minutes_completed)}`,
          );
          label.fontFace = "ui-monospace, Menlo, monospace";
          label.color = goalColor[n.goal_id];
          label.textHeight = 5;
          label.fontWeight = "bold";
          label.position.y = radius + 8;
          group.add(label);
        }
        return group;
      })
      // Task → goal lines take the goal's colour. Goal ↔ goal "worked the same
      // day" lines (week view, Unit 21) are neutral, and thicker the more days
      // the two goals shared.
      .linkColor((l) =>
        l.kind === "shared_day"
          ? tokens.muted
          : goalColor[typeof l.target === "object" ? l.target.goal_id : ""],
      )
      .linkOpacity(0.35)
      .linkWidth((l) => (l.kind === "shared_day" ? 0.4 + l.weight * 0.35 : 0))
      .linkLabel((l) =>
        l.kind === "shared_day"
          ? `${l.source.label} & ${l.target.label}: worked the same day on ${l.weight} day${l.weight === 1 ? "" : "s"}`
          : "",
      )
      // Frame every cluster once the layout has settled.
      .cooldownTicks(120)
      .onEngineStop(() => graph.zoomToFit(600, 40))
      .graphData({
        // 3d-force-graph mutates what it is given; hand it copies.
        nodes: data.nodes.map((n) => ({ ...n })),
        links: data.links.map((l) => ({ ...l })),
      });

    // Shared-day links are long and loose, so clusters stay readable as
    // clusters instead of collapsing into one ball.
    graph
      .d3Force("link")
      .distance((l) => (l.kind === "shared_day" ? 140 : 30))
      .strength((l) => (l.kind === "shared_day" ? 0.05 : 1));

    const onResize = () => graph.width(el.clientWidth).height(el.clientHeight);
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      graph.pauseAnimation();
      graph._destructor();
      el.replaceChildren();
    };
  }, [data]);

  const now = new Date();
  const todayIso = shiftDate(`${now.getFullYear()}-${now.getMonth() + 1}-${now.getDate()}`, 0);
  const step = mode === "day" ? 1 : 7;
  const atLatest = mode === "day" ? date >= todayIso : shiftDate(monday, 7) > todayIso;
  const unit = mode === "day" ? "day" : "week";

  return (
    <section className="day-graph">
      <div className="day-graph-header">
        <button className="day-graph-nav" onClick={onBack}>
          ← Today
        </button>
        <div className="day-graph-date">
          <button
            className="day-graph-nav"
            onClick={() => setDate(shiftDate(date, -step))}
            aria-label={`Previous ${unit}`}
          >
            ‹
          </button>
          <h2>{mode === "day" ? formatLongDate(date) : formatWeek(monday)}</h2>
          <button
            className="day-graph-nav"
            onClick={() => setDate(shiftDate(date, step))}
            disabled={atLatest}
            aria-label={`Next ${unit}`}
          >
            ›
          </button>
        </div>
        <div className="graph-mode" role="group" aria-label="Graph range">
          {["day", "week"].map((m) => (
            <button
              key={m}
              className={`graph-mode-button ${mode === m ? "active" : ""}`}
              onClick={() => setMode(m)}
              aria-pressed={mode === m}
            >
              {m === "day" ? "Day" : "Week"}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="loading">Loading…</div>}
      {!loading && result.error && <div className="error">Error: {result.error}</div>}
      {!loading && data && data.nodes.length === 0 && (
        <p className="empty">No tasks {mode === "day" ? "on this day" : "this week"}.</p>
      )}
      {!loading && data && data.nodes.length > 0 && (
        <>
          <div className="day-graph-canvas" ref={containerRef} />
          <p className="day-graph-hint">Drag to rotate · scroll to zoom</p>
          {/* The same numbers as text: readable without WebGL, and exact. Goals
              arrive ranked by time completed, so this is also the answer to
              "which goal got the most work". */}
          <h3 className="day-graph-legend-title">
            Most time {mode === "day" ? "today" : "this week"}
          </h3>
          <ol className="day-graph-legend">
            {goals.map((g, i) => (
              <li key={g.id}>
                <span className="day-graph-rank">{i + 1}</span>
                <span className={`day-graph-swatch goal-color-${g.color_slot}`} />
                <strong>{g.label}</strong>
                <span>
                  {formatMinutes(g.minutes_completed)} of {formatMinutes(g.minutes_planned)} ·{" "}
                  {g.completed_count}/{g.task_count} done
                </span>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
