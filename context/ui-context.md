# UI Context

Recovered from `frontend/src/styles/dashboard.css` and the components on
2026-09-07. This documents the design that exists. Where components bypass the
token system, that is recorded as a divergence, not promoted to a standard.

## Design Intent

A dark, dense scoreboard. Chris opens it on a phone in the morning and on a
laptop during the day, for thirty seconds at a time, to answer two questions:
what do I owe today, and is the chain still alive. It is a mirror, not a coach —
so the visual language is numbers and status color, with no illustration, no
celebration, and no motivational surface. Green and red carry all the emotional
weight; everything else stays quiet.

## Color Tokens

Defined once in `:root` in `frontend/src/styles/dashboard.css`. Nine tokens,
147 `var()` references.

| Role | Token | Value |
| ---- | ----- | ----- |
| Page ground | `--bg` | `#0a0d12` |
| Raised surface | `--bg-secondary` | `#141820` |
| Primary text | `--fg` | `#f0f0f0` |
| Secondary text | `--muted` | `#888` |
| Pending rep | `--pending` | `#555` |
| Completed rep | `--completed` | `#4ade80` |
| Missed rep | `--missed` | `#ef4444` |
| Divider | `--border` | `#1a2332` |
| Elevation | `--shadow` | `rgba(0, 0, 0, 0.3)` |
| Heatmap, no reps | `--heat-0` | `#222222` |
| Heatmap, low | `--heat-1` | `#4ade80` |
| Heatmap, medium | `--heat-2` | `#22c55e` |
| Heatmap, high | `--heat-3` | `#16a34a` |

The heat ramp is an intensity scale, not a status. It deliberately does not
reuse `--completed`, whose meaning is "this rep was done".

**Dark only. There is no light mode and no `prefers-color-scheme` handling — do
not add one speculatively.**

The three status colors are semantic and mirror the Google Calendar mapping
exactly. Keep them aligned: `pending` = graphite (`colorId` 8), `completed` =
basil (`colorId` 10), `missed` = tomato (`colorId` 11). Changing one without the
other breaks the mirror.

**Resolved 2026-09-07: no raw hex remains in any component.** Every SVG
`stroke`/`fill` and every inline `style` colour is a `var(--…)`, and `:root` is
the only place a colour is defined. A wrong token name renders transparent
rather than erroring, so verify computed styles in a browser after touching one
— checking the markup is not enough.

## Typography

| Role | Family | Token |
| ---- | ------ | ----- |
| Interface | `-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif` | none — declared on `.dashboard` |
| Code / data | none | — |

System font stack, no webfont, no `--font-*` token. `line-height: 1.6` on
`.dashboard`. Sizes are set per component in `rem` with no named scale; stat
values are the largest type on the page and carry the hierarchy.

## Spacing and Radius

- **Spacing base:** `rem`, in `0.25` steps. `.dashboard` padding is `1.5rem`,
  rising to `2rem 3rem` above 768px.
- No `--radius-*` tokens. Radii are set per component; match the neighbouring
  component rather than inventing a value.

## State Coverage

Every fetching view implements loading and error. `Dashboard`, `Analytics`,
`Debrief`, `History`, `WeekView`, `RepScheduling` and `GoalsManagement` all
follow the same three-piece shape.

| State | What renders |
| ----- | ------------ |
| Empty | A `.empty` paragraph naming what is missing — "No reps scheduled for today.", "No reps for this goal today." Never a bare panel. |
| Loading | `<div className="loading">Loading…</div>` replacing the section body. No skeletons, no optimistic updates. |
| Error | `<div className="error">Error: {message}</div>`. The message is the `Error` thrown by `api.js`, which is a fixed human string per endpoint ("Failed to fetch summary") — never a raw exception or a status code. |
| Partial | Not handled. `/summary` is one request, so it either fully arrives or fully fails. Sections whose data is empty fall through to their empty state — `goal_progressions` renders its sidebar only when non-empty. |

## Feedback and Latency

The current pattern, stated plainly: **there is no inline latency feedback on
mutations.** A rep completion fires, then the whole summary is refetched, and the
view shows `Loading…` for the duration. Outcomes are announced with `alert()`.

| Duration | Response |
| -------- | -------- |
| Any mutation | No per-element indicator. The parent refetches and the section drops to `Loading…`. |
| Success | Silent for completions. `alert()` for the end-of-day sweep. |
| Failure | `alert("Failed: " + message)` — 19 `alert()` calls across the components. |

`TodayTasks` follows the same convention with one refinement: after a
check-off only the task list refetches, not the whole summary. Its sync
failure is a muted `.tasks-note`, never `.error` or `--missed` — the list is
still usable from saved data.

This is the observed convention, and it is honest but crude: completing a rep
that also patches a Google Calendar event can take a second or more with no
feedback on the button pressed. Improving it is a real unit; until then, match
the existing pattern rather than introducing a second one.

## Destructive Actions

Confirmed with the browser's `confirm()`. No undo anywhere — every destructive
action is final.

- **Delete a rep** — `confirm("Delete this rep? This cannot be undone.")` in
  `TodayReps.jsx:24` and `WeekView.jsx:41`. Note this action violates a product
  invariant (see `architecture.md` Known Violations); the confirmation does not
  make it correct.
- **Archive a goal** — `confirm("Archive this goal? (Data will be preserved)")`.
- **Hard-delete a goal** — a second, separate confirmation. The only path that
  destroys reps.
- **Archive a rep type** — `confirm("Archive this rep type?")`.

## Components

Hand-written React 19 function components, one per file, default-exported, in
`frontend/src/components/`. No component library, no `forwardRef`, no
`useContext`, no custom hooks, no memoization. Props are plain and explicit —
data down, callbacks up (`onRepComplete`, `onViewChange`). Nothing is generated,
so nothing is off-limits to hand-editing.

`ChainsList.jsx` and `ChainsVisualization.jsx` are written and unused — wiring
them into `Dashboard` is the intended next change, not a rewrite.

## Layout Patterns

- **Shell** — `.dashboard` wraps everything: an `h1` header, `<Nav>`, then one
  of seven views. `Dashboard.jsx` is the only stateful container; view selection
  is `useState`, not a router, so there are no deep links and the browser back
  button does not move between views.
- **Today** — since Unit 20, `.dashboard-main` holds only the date (a button
  opening the graph) and `TodayTasks`. Every rep widget was removed.
- **Task row** — `TaskItem` (since Unit 17): the same `○` / `✓` / `✗` status
  button as a rep row, the task title, then `9:00 AM–10:30 AM · 1h30` or
  `All day · 24h`. Its CSS is shared with `.rep` through combined selectors,
  not copied. No delete button: tasks are removed by deleting the calendar
  event.
- **Task graph** — `TaskGraph` (Units 18–19), reached by clicking Today's
  date, not from Nav. A Day / Week switch (`.graph-mode`); the legend is a
  ranked list of goals by time completed. Goal colours come from the API's
  `color_slot`, fixed per goal, never from rank. A `3d-force-graph` WebGL canvas, 70vh, lazy-loaded. Goals are
  labelled hubs coloured `--goal-1…6` by rank of time spent; completed tasks
  glow in their goal's colour, missed are `--missed` wireframes, pending are
  `--pending` with no glow. WebGL reads the tokens from `:root` at runtime —
  no colour is defined in JS. A text legend repeats every number.
- **Nav** — a flat row of five `.nav-button`s (Today, Goals, History,
  Analytics, Week); the active one gets `.active`. Below 768px the buttons
  tighten so the row fits at 360px, and it wraps rather than scrolling the page.
- **Rep row** — `RepItem`: a status button (`○` / `✓` / `✗`, disabled unless
  pending), `[RepType]` in brackets, the time, then a delete `✕`. The bracket
  prefix matches the calendar event title format on purpose.
- **Charts** — hand-rolled inline SVG with an explicit `viewBox`,
  `vectorEffect="non-scaling-stroke"`, and a `margin` object. No charting
  library. Chain and progression charts are 240×100; history is 1200×200.
- **Breakpoints** — one, at `min-width: 768px`, which widens `.dashboard`
  padding. Mobile-first single column below it.

## Icons

No icon library. Status and actions are Unicode glyphs rendered as text:
`○` pending, `✓` completed, `✗` missed, `✕` delete. `frontend/public/icons.svg`
and `favicon.svg` exist and are not referenced by any component. Rep-type emoji
are user-supplied data (`RepType.emoji`, `String(8)`), not part of the icon
system.
