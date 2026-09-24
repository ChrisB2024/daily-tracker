# Build Plan 2 — Calendar First

Decided 2026-09-24. Replaces the direction of `00-build-plan.md`, whose thirteen
units are all shipped. Units are numbered on from 14 and land in order, one at a
time, each verified against a real Postgres before the next starts.

## Why

The tracker was the place work got planned: create a rep in the app, it appears
gray in Google Calendar. In practice Chris plans in Google Calendar, so the app
became a second place to type the same thing, and it stopped being productive.

The flow is now inverted:

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
| `start_time`, `end_time` | time | all-day events: see Open Questions |
| `duration_minutes` | int | `end − start`; the graph's weight |
| `status` | enum `pending / completed / missed` | same state machine as reps |
| `completed_at` | timestamptz, nullable | |
| `created_at`, `updated_at` | timestamptz | |

### Rules carried over unchanged

- `pending → completed` and `pending → missed` only, both terminal. Status is
  never a writable field.
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
**Done when:** a `[Goal] x` event created by hand in Google appears from
`GET /tasks` after one sync · syncing twice creates no duplicate · a
`[Nonexistent] x` event is reported as unmatched · an old rep event is not
imported · moving a completed task's event does not move the task.

### Unit 16 — Check off and sweep

**Builds:** `POST /tasks/{id}/complete` (409 unless pending) patching the event
green, and the existing 23:59 sweep extended to mark pending tasks `missed` and
patch them red. Reuses `patch_color`.
**Done when:** checking a task turns its event green · a task left unchecked is
red the next morning without pressing anything · completing twice returns 409.

### Unit 17 — The daily list

**Builds:** Today becomes the day's tasks grouped by goal, each with a checkbox,
plus a sync button and the last-synced time. Required empty, loading and error
states. Nothing else on Today changes in this unit.
**Done when:** Chris opens Today, sees what is on his calendar today, and
checking one turns it green in Google.

### Unit 18 — Day graph

**Builds:** clicking a day opens a screen where each goal is a node and each
task is a point joined by a line to its goal. Tasks that share a goal are
connected through that goal's node, so a cluster reads as "this goal". Goal
node size is minutes completed that day. Missed tasks are drawn, hollow, never
omitted. Backend: `GET /tasks/graph?date=` returns nodes and edges.
**Rendering:** hand-written SVG with a deterministic layout (goals on a ring,
tasks fanned around their goal) — no graph library. The existing charts are
hand-written SVG, the layout is explainable in one paragraph, and it does not
reshuffle every time the page loads. Revisit only if it reads badly.
**Blocked on:** a look at the skill-graph project it should resemble.

### Unit 19 — Week view by goal

**Builds:** the same points-and-lines view over Mon–Sun, goal nodes sized by
minutes completed that week, and a ranked list beside it answering "which goal
got the most time this week". `GET /tasks/graph?week_start=`.

### Unit 20 — Retire the rep UI

**Builds:** Schedule view and rep-type management removed from the nav; goals
management stays (tasks need goals). History keeps rendering past reps
read-only. No rep row is touched and no rep column is dropped.
**Not in this unit:** deleting rep code paths the history still reads.

## Not units yet

- **The Sunday debrief.** It is built from reps and chains. Rebuilding it on
  tasks, or retiring it, is its own decision — see Open Questions.
- **Chains.** Chains are per rep type; tasks have no rep type. Whether tasks
  get a per-goal chain is undecided.
- **Push notifications from Google** (watch channels) instead of polling.
  Polling every 15 minutes plus a sync button is enough for one user and far
  easier to explain and debug.

## Open Questions

Logged in `progress-tracker.md` too. Do not answer these on your own.

1. **The skill-graph project.** Where is it? Unit 18 should copy its look, not
   guess at it.
2. **All-day events.** A `[Goal] x` event with no time — a task with duration 0,
   a task with a default duration, or ignored?
3. **Event deleted in Google while its task is pending.** Delete the task
   (nothing was done), or keep it and let the sweep mark it missed?
4. **Checking off late.** The sweep runs at 23:59. Checking off after midnight
   hits a missed task and gets a 409. Is that right, or is there a grace window
   (e.g. until noon the next day)?
5. **Which Google calendars are read.** Only the primary calendar, or every
   calendar on the account?
6. **The debrief and chains** — rebuild on tasks, keep on history, or retire?
