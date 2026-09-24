import { useEffect, useRef, useState } from "react";
import ForceGraph3D from "3d-force-graph";
import SpriteText from "three-spritetext";
import * as THREE from "three";
import { getTaskGraph } from "../api";

// Lazy-loaded from Dashboard: three.js is large, and Today should not pay for it.

// "2026-09-24" ± n days, done on the calendar date alone so no timezone can
// shift it (same reason as parseISODate in Dashboard).
function shiftDate(iso, days) {
  const [y, m, d] = iso.split("-").map(Number);
  const next = new Date(y, m - 1, d + days);
  const pad = (n) => String(n).padStart(2, "0");
  return `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
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

export default function DayGraph({ initialDate, onBack }) {
  const [date, setDate] = useState(initialDate);
  const [result, setResult] = useState({ date: null, data: null, error: null });
  const containerRef = useRef(null);

  useEffect(() => {
    getTaskGraph(date)
      .then((data) => setResult({ date, data, error: null }))
      .catch((err) => setResult({ date, data: null, error: err.message }));
  }, [date]);

  const loading = result.date !== date;
  const data = loading ? null : result.data;
  const goals = data ? data.nodes.filter((n) => n.kind === "goal") : [];

  // Build the 3D scene whenever a day's data arrives; tear it down on change.
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !data || data.nodes.length === 0) return;

    const tokens = readTokens();
    // Goals arrive most-time-first, so colours are stable for a given day.
    const goalColor = {};
    data.nodes
      .filter((n) => n.kind === "goal")
      .forEach((g, i) => {
        goalColor[g.goal_id] = tokens.goals[i % tokens.goals.length];
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
      .linkColor((l) => goalColor[typeof l.target === "object" ? l.target.goal_id : ""])
      .linkOpacity(0.35)
      .linkWidth(0)
      // Frame every cluster once the layout has settled.
      .cooldownTicks(120)
      .onEngineStop(() => graph.zoomToFit(600, 40))
      .graphData({
        // 3d-force-graph mutates what it is given; hand it copies.
        nodes: data.nodes.map((n) => ({ ...n })),
        links: data.links.map((l) => ({ ...l })),
      });

    const onResize = () => graph.width(el.clientWidth).height(el.clientHeight);
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      graph.pauseAnimation();
      graph._destructor();
      el.replaceChildren();
    };
  }, [data]);

  const today = new Date();
  const todayIso = shiftDate(
    `${today.getFullYear()}-${today.getMonth() + 1}-${today.getDate()}`,
    0,
  );

  return (
    <section className="day-graph">
      <div className="day-graph-header">
        <button className="day-graph-nav" onClick={onBack}>
          ← Today
        </button>
        <div className="day-graph-date">
          <button
            className="day-graph-nav"
            onClick={() => setDate(shiftDate(date, -1))}
            aria-label="Previous day"
          >
            ‹
          </button>
          <h2>{formatLongDate(date)}</h2>
          <button
            className="day-graph-nav"
            onClick={() => setDate(shiftDate(date, 1))}
            disabled={date >= todayIso}
            aria-label="Next day"
          >
            ›
          </button>
        </div>
        <span className="day-graph-hint">Drag to rotate · scroll to zoom</span>
      </div>

      {loading && <div className="loading">Loading…</div>}
      {!loading && result.error && <div className="error">Error: {result.error}</div>}
      {!loading && data && data.nodes.length === 0 && (
        <p className="empty">No tasks on this day.</p>
      )}
      {!loading && data && data.nodes.length > 0 && (
        <>
          <div className="day-graph-canvas" ref={containerRef} />
          {/* The same numbers as text: readable without WebGL, and exact. */}
          <ul className="day-graph-legend">
            {goals.map((g, i) => (
              <li key={g.id}>
                <span className={`day-graph-swatch goal-color-${(i % 6) + 1}`} />
                <strong>{g.label}</strong>
                <span>
                  {formatMinutes(g.minutes_completed)} of {formatMinutes(g.minutes_planned)} ·{" "}
                  {g.completed_count}/{g.task_count} done
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
