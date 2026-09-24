# Build Plan 2 — Calendar First

Decided 2026-09-24. Replaces the direction of `00-build-plan.md`, whose thirteen
units are all shipped. Units are numbered on from 14 and land in order, one at a
time, each verified against a real Postgres before the next starts.

## Why

The tracker was the place work got planned: create a rep in the app, it appears
gray in Google Calendar. In practice Chris plans in Google Calendar, so the app
became a second place to type the same thing, and it stopped being productive.

Each side is good at one half. Putting a task on the calendar is fast;
typing it into the tracker's UI is slow. Ticking a checkbox in the tracker is
fast; marking something done on the calendar is awkward. So the flow is
inverted to give each side the half it is good at:

> **Google Calendar is the input. The tracker is the scoreboard.**

Chris puts tasks on his calendar. The tracker pulls them into a daily list,
unchecked. At the end of the day he checks off what he did. Checked tasks turn
the calendar event green; unchecked ones are swept to missed and turn it red.
Clicking a day opens a graph of that day's work — tasks as points, joined by
lines to the goals they serve — and a week view shows which goal got the most
time.

## Decisions (Chris, 2026-09-24)

| Question | Answer |
| -------- | ------ |
| How does an event know its goal? | **Title prefix.** `[Goal title] what I'm doing`, e.g. `[Hitwin] ship onboarding`. Matched case-insensitively against active goal titles. Events with no prefix are ignored — meetings and personal events never enter the tracker. |
| A task not checked off by end of day? | **Missed, and the event turns red.** Same as reps today: the 23:59 sweep marks it `missed` and patches the event to `colorId 11`. It stays visible as missed. |
| What does "worked more" mean in the graph? | **Time spent.** Sum of the durations of *completed* tasks per goal. A 3h block outweighs a 20-minute one. |
| All-day events? | **Match the length on the calendar.** Duration is the event's span as Google stores it, so a one-day all-day event is 1440 minutes. |
| Event deleted in Google while its task is pending? | **The task disappears from the checklist, and Chris gives a reason.** The row is kept as `cancelled`; at end of day the tracker lists the day's cancelled tasks and asks why each one was removed. |
| When can a task be checked off? | **Until midnight.** The sweep runs at 00:00 and marks the previous day's unchecked tasks missed and red. |
| Which calendars? | **The primary calendar only.** |
| Debrief and chains? | **Drop them for now.** Both are built on reps; neither is rebuilt on tasks. |
| The current rep system? | **Keep history, retire UI.** Every existing rep row stays in the database and stays visible in History. The Schedule screen and rep-type management go away. Tasks link straight to a goal — no rep type. |

## Domain

**Goal → Task.** A **task** is one Google Calendar event, tagged to a goal by
its title prefix, with a binary outcome. It is a new entity, not a rep:

- A rep requires a `rep_type_id` (NOT NULL). A task has no rep type. Making
  `rep_type_id` nullable would rewrite a column on `reps`, which needs explicit
  approval and buys nothing — the old history is finished data.
- Keeping them apart means the reps table is never touched by this plan.

Proposed `tasks` table (Unit 14 finalises it):

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | UUID PK | |
| `goal_id` | UUID FK → goals, NOT NULL | resolved from the title prefix |
| `calendar_event_id` | text, NOT NULL, **UNIQUE** | the event is the identity; re-syncing must upsert, never duplicate |
| `title` | text | the event title with the `[Goal]` prefix stripped |
| `scheduled_date` | date | in `settings.tz` |
| `start_time`, `end_time` | time, nullable | null for all-day events |
| `duration_minutes` | int | the event's length on the calendar, all-day included; the graph's weight |
| `is_all_day` | bool | all-day events carry no start/end time |
| `status` | enum `pending / completed / missed / cancelled` | see state machine below |
| `cancel_reason` | text, nullable | written by Chris after the event was deleted |
| `completed_at` | timestamptz, nullable | |
| `created_at`, `updated_at` | timestamptz | |

### Task state machine

```
pending --checkbox (before midnight)--> completed   event → green
pending --00:00 sweep-----------------> missed      event → red
pending --event deleted in Google-----> cancelled   needs a reason
```

All three are terminal. Status is never a writable field. `cancel_reason` is
the only field Chris writes on a cancelled task, and only while it is empty.
Cancelled tasks leave the checklist and the graph; they appear in an end-of-day
"removed today — why?" list until each has a reason. `cancel_reason` is free
text in an unauthenticated database (S2): the input says so, and it is
one line, not a journal.

### Rules carried over unchanged

- Missed tasks are never deleted or hidden.
- All date math in `settings.tz`.
- A Google call never raises into a request handler.
- Metrics (time per goal, counts) are computed at read time, never stored.

### Rules that flip

These are the reason this plan exists. Each is updated in `architecture.md`
and `project-overview.md` in the unit that makes it true, not before.

- **Product 5 — "the calendar is a mirror, never a source."** Becomes: *the
  calendar is the source of what was planned; the tracker is the source of
  what was done.* Reading an event may create or reschedule a **pending**
  task. Nothing read from Google may ever change a completed or missed task —
  the evidence rule survives the flip.
- **Security 3 — "write-only".** The OAuth scope stays `calendar.events`,
  which already grants read; no new consent is needed. The rule becomes
  "scoped to `calendar.events`, reads events and patches their color, never
  creates or deletes an event the user made".
- **Never: two-way calendar sync.** Moves off the Never list.

### The one trap

The old system wrote events titled `[RepType] Goal title` carrying
`extendedProperties.private.rep_id`. A `[Build project] Angle` event would
otherwise parse as a task for a goal called "Build project". The importer
**must skip any event that carries a `rep_id` private property.**

## Units

### Unit 14 — `tasks` table

**Builds:** the model, schema and an additive Alembic revision. No endpoint, no
UI. **Boundary:** `models/` + `alembic/versions/`.
**Done when:** `alembic upgrade head` then `downgrade -1` then `upgrade head`
round-trips on a scratch database · the `reps` table is byte-for-byte
unchanged · inserting two tasks with one `calendar_event_id` fails.

### Unit 15 — Pull tasks from the calendar

**Builds:** `GoogleCalendarClient.list_events(start, end)`, a
`services/task_sync.py` that parses the prefix, resolves the goal and upserts
tasks, `POST /tasks/sync?date=` and `GET /tasks?date=`. A scheduler job runs the
sync every 15 minutes for today and tomorrow.
**Sync rules:** new tagged event → pending task · moved or renamed event → update
the task **only while pending** · untagged or unknown-goal event → skipped and
counted in the sync response, not silently dropped · event with a `rep_id` →
skipped.
Primary calendar only. A pending task whose event is gone from Google becomes
`cancelled`.
**Done when:** a `[Goal] x` event created by hand in Google appears from
`GET /tasks` after one sync · syncing twice creates no duplicate · a
`[Nonexistent] x` event is reported as unmatched · an old rep event is not
imported · moving a completed task's event does not move the task · deleting
a pending task's event cancels it; deleting a completed one changes nothing ·
an all-day event imports with its calendar length.

### Unit 16 — Check off, sweep, and removal reasons

**Builds:** `POST /tasks/{id}/complete` (409 unless pending) patching the event
green; a 00:00 job in `settings.tz` marking the previous day's pending tasks
`missed` and patching them red (the rep sweep stays at 23:59 until Unit 20);
`POST /tasks/{id}/cancel-reason` (409 unless cancelled with no reason yet).
Reuses `patch_color`.
**Done when:** checking a task turns its event green · a task left unchecked is
red the next morning without pressing anything · completing twice returns 409 ·
a task checked at 23:58 stays completed · a reason can be written once.

### Unit 17 — The daily list

**Builds:** Today becomes the day's tasks grouped by goal, each with a checkbox,
plus a sync button, the last-synced time, and the "removed today — why?" list
with one reason input per cancelled task. Required empty, loading and error
states. Nothing else on Today changes in this unit.
**Done when:** Chris opens Today, sees what is on his calendar today, and
checking one turns it green in Google.

### Unit 18 — Day graph

**Builds:** clicking a day opens a screen where each goal is a labelled cluster
and each task is a glowing point joined by a line to its goal; tasks that share
a goal are connected through it, so a cluster reads as "this goal". Backend:
`GET /tasks/graph?date=` returns nodes and edges.

**Reference look** (Chris's Lobe Atlas screenshot, 2026-09-24): near-black
background; small glowing dots with a soft halo; thin low-opacity lines; each
cluster tinted its own color and labelled in caps with a subtitle
("HITWIN — 4 tasks · 3h10"); monospace labels; a faint dust of tiny points
for depth; **drag to rotate, scroll to zoom** — a 3D point cloud, not a flat
chart.

Mapping: goal = cluster and hub node, sized by minutes completed · task = point,
sized by its duration · completed = bright, missed = red, hollow · pending
(today) = dim. Cancelled tasks are not drawn.

**Rendering:** hand-written `<canvas>` with a small 3D projection — goal hubs
placed on a sphere, tasks scattered around their hub, points rotated by the
drag angle and projected with perspective each frame. Roughly 200 lines Chris
can read top to bottom, no dependency. The alternative is `3d-force-graph`
(three.js), which gives this look almost for free but is a large dependency
whose physics he would not be able to explain. Decide at the start of the unit.

### Unit 19 — Week view by goal

**Builds:** the same points-and-lines view over Mon–Sun, goal nodes sized by
minutes completed that week, and a ranked list beside it answering "which goal
got the most time this week". `GET /tasks/graph?week_start=`.

### Unit 20 — Retire the rep UI

**Builds:** Schedule view and rep-type management removed from the nav; goals
management stays (tasks need goals). History keeps rendering past reps
read-only. No rep row is touched and no rep column is dropped.
Chains leave Today, the Debrief view leaves the nav, and the Sunday debrief
job and 23:59 rep sweep stop being registered.
**Not in this unit:** deleting rep code paths the history still reads.

## Not units yet

- **The Sunday debrief and chains** — dropped for now (2026-09-24). Unit 20
  removes the chains from Today and turns off the Sunday job. Past
  `weekly_summaries` rows are kept.
- **Push notifications from Google** (watch channels) instead of polling.
  Polling every 15 minutes plus a sync button is enough for one user and far
  easier to explain and debug.

## Open Questions

Answered 2026-09-24 — see the Decisions table. Still open:

1. **A removal reason never given.** If Chris does not write a reason for a
   cancelled task, does the list keep asking on following days, or does it
   expire? Blocks Unit 17's list, not Unit 16.
