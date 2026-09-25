# Progress

Update after every meaningful change. This file is how a cold session recovers
full context in one read.

Reconstructed on 2026-09-07 from the code, `readme.md`'s build order, and git
history. Nothing here was verified against a running instance — the state of
the live Railway deploy is recorded as Chris reported it.

## Phase

**Redesign: calendar first** (decided 2026-09-24). V1 is shipped and in daily
use, but planning in the app and mirroring to Google Calendar stopped being
productive — Chris plans in Google Calendar. The flow inverts: calendar events
tagged `[Goal] …` are pulled in as **tasks**, checked off at end of day, and
shown as a points-and-lines graph per day and per week. The plan is
`context/specs/14-calendar-first-redesign.md` (Units 14–20).

Everything below **Shipped** describes the rep system, which keeps running
until Unit 20 retires its UI. Its data is kept forever.

## Working On

**Unit 18 (day graph) merged to `main` on 2026-09-24** at Chris's
instruction. After Railway finishes deploying, refresh once — the graph calls
the new `/tasks/graph`. Still to check on real hardware: the halo glow and a
black background on Chris's Mac — **confirmed by Chris 2026-09-24**.

**Unit 19 (week view) merged to `main` on 2026-09-24** at Chris's
instruction.

**Unit 20 (retire the rep UI) merged to `main` on 2026-09-24** at Chris's
instruction. **Build Plan 2 is complete.**

**Build Plan 3** (`context/specs/15-goal-links-and-push.md`, Units 21–24):
goal links in the week graph, then push notifications to Chris's iPhone.
**Units 21–24 merged to `main` on 2026-09-25** at Chris's instruction —
Build Plan 3 is complete. **Push is live in production** (2026-09-24): VAPID
variables set on Railway, the three notification jobs scheduled, and Chris
installed the app on his iPhone, subscribed, and received a test push.

**Units 14–17 merged to `main` on 2026-09-24** at
Chris's instruction, so the calendar-first flow is live (Railway runs
revision `8fcad7e710dc` on deploy; Vercel ships the new Today). **Confirmed
working in production by Chris on 2026-09-24**: `GET /tasks` answered `[]`
after the deploy, and after a refresh Today synced and showed tasks from his
real calendar. This was the redesign's first contact with real Google.

## Shipped

- **Slice 1 — Foundation.** FastAPI + async SQLAlchemy 2 + Postgres. Three
  tables (`goals`, `rep_types`, `reps`) with both FKs NOT NULL on `reps`. Goal
  CRUD with soft-archive and an explicit `?hard=true` purge. RepType CRUD nested
  under goals, soft-archive only. Rep create (single and bulk), complete with a
  409 guard, manual mark-missed sweep, delete. Two Alembic revisions, both
  applied.
- **Slice 2 — Calendar.** `scripts/google_oauth.py` obtains a refresh token by
  hand. `GoogleCalendarClient` wraps Calendar API v3 in `asyncio.to_thread`,
  scoped write-only to `calendar.events`. Events are created gray with a
  `[RepType] Goal title` summary and `extendedProperties.private.rep_id`,
  patched green on complete and red on the missed sweep, and deleted with the
  rep. Every operation degrades to a warning instead of raising.
- **Slice 3 — Dashboard.** React 19 + Vite SPA with seven views. `GET /summary`
  returns daily score, week total, all-time weekly PR, first-rep rate, chains
  with 60-day history, today's reps grouped by goal, a month heatmap, and
  per-goal progressions. Today renders all of it **except the chains**.
- **Slice 4 — Debrief.** `GET /debrief` aggregates the week, generates prose via
  the `anthropic` SDK, converts it to MP3 via ElevenLabs, and returns text plus
  base64 audio plus stats. An APScheduler cron job emails text + MP3 attachment
  via Gmail SMTP. Delivered as email rather than the push notification the
  readme specified.
- **Slice 5 — Quality of life.** Full goal and rep-type management UI including
  archived-item toggle and inline editing. Rep scheduling with a recurring
  "next N days" option. History view with all-time per-goal progression charts.
  Plus three views beyond the original scope: Analytics (per-rep-type completion
  rates), WeekView (Mon–Sun with inline complete and delete), and goal
  progression charts.
- **Unit 01 — Guard rep deletion** (2026-09-07). `DELETE /reps/{id}` returns 409
  for completed and missed reps; the ✕ renders only on pending rows. Product
  invariant 3 now holds for every path reachable from the UI.
- **Unit 02 — Fix chain computation** (2026-09-07). One forgiven empty day per
  chain, length as calendar span, today never judged. Archived rep types
  excluded; rep types with no completions emitted at 0 instead of vanishing.
  Weekly-only chaining still carved out — no live case.
- **Archive + delete fixes** (2026-09-07, out of band, not a numbered unit).
  `GET /goals/{id}/rep-types` returns active only unless `?include_archived=true`,
  so archiving a rep type now removes it from management and from the scheduling
  dropdown instead of doing nothing visible. Goal hard-delete deletes the
  calendar events of the reps it purges, matching what single-rep delete already
  did. Three direct React state mutations (`delete repTypes[goalId]`) replaced
  with a forced reload.
- **Unit 03 — Render chains on Today** (2026-09-07). Live chains lead, sorted
  longest first; the 46 at zero collapse behind a one-click summary line naming
  how many have never been completed. Sparklines for live chains only. All
  hardcoded hex in both components replaced with tokens.
- **Unit 04 — One week, one timezone** (2026-09-07). One `week_start_for()`
  helper in `services/summary.py`, imported by `debrief.py`, replacing five
  separate week calculations of which one disagreed. Scheduler pinned to
  `settings.tz` and startup now logs the resolved next fire time. Frontend
  `Dashboard` and `ChainsList` parse ISO dates as local, fixing a header that
  showed yesterday.
- **Unit 05 — End-of-day sweep** (2026-09-07). A 23:59 job in `settings.tz`
  closes out the day; sweep logic moved out of the router into
  `services/sweep.py` and shared by both callers. The manual endpoint now sweeps
  only days that have **ended**, so pressing it in the morning no longer marks
  today's pending reps missed. The sweep job registers even when email is not
  configured.
- **Unit 06 — Fix `first_rep_rate`** (2026-09-07). Per goal, measured on
  `completed_at` before local noon rather than `scheduled_time`, over days a
  first rep was actually scheduled. Archived rep types and non-active goals
  excluded. `first_rep_rate: float` in `/summary` became
  `first_rep_rates: [{goal_id, goal_title, rate, days_hit, days_scheduled}]`,
  with `rate: null` for "none scheduled" — which is not 0%. `FirstRepStrip`
  renders one bar per goal.
- **Smoke test** (2026-09-07, out of band). `backend/scripts/smoke.py` — a
  dependency-free read-only checker over every GET endpoint, response shape and
  the no-orphan-reps invariant. Verified it catches the Unit 06 regression by
  reverting `_walk_chain` and watching `/summary` fail. 36/36 local, 76/76
  against production.
- **Unit 07 — Debrief inputs** (2026-09-07). `get_weekly_summary_data` now
  returns per-rep-type chains with their change since last week, chains that
  broke and on which day, week total against the all-time PR with a beat /
  matched / below verdict, per-goal first-rep rates, and the most-completed and
  most-avoided rep types — the last ranked by completed-against-expected, not
  raw count. `get_chains` gained an `as_of` date; `_walk_chain` became public
  `walk_chain` so the debrief walks identical semantics rather than a copy.
- **Unit 08 — Debrief prompt and tone** (2026-09-07). Findings, not
  encouragement: prohibitions stated as absolute rules with `readme.md`'s own
  worked example as the voice anchor, fed the full Unit 07 payload. Model
  `claude-opus-4-8` -> `claude-opus-5` with adaptive thinking, `max_tokens`
  300 -> 2000. `stop_reason` checked for refusal and truncation. A failed call
  returns a fixed sentence instead of the exception string, which previously
  would have emailed an auth error as that week's debrief.
- **Unit 09 — Kill the N+1s** (2026-09-07). `/summary` 63 -> 27 queries and
  115ms -> 41ms; `get_week_reps` 46 -> 3 queries. Counts moved into SQL,
  `get_weekly_pr` groups by week in Postgres, `selectinload` replaced every
  `refresh`-in-a-loop, and the router's per-chain and per-goal fan-outs became
  two batch queries. One `GoogleCalendarClient` per bulk request, with its
  service cached per instance.
- **Unit 10 — Calendar sync integrity** (2026-09-07). A failed event creation
  is logged at error naming the rep, and the rep surfaces a muted marker in
  Today and Week instead of being silently unsynced. Rescheduling a rep now
  moves its calendar event via a new `patch_time`; editing only `notes` makes no
  call. `/summary` carries `calendar_enabled` and each rep's
  `calendar_event_id`, so the UI can tell "sync failed" from "sync is off".
- **Unit 13 — Delete dead code** (2026-09-07, three commits). The unregistered
  Jinja dashboard, its template, stylesheet, `StaticFiles` mount and the
  `jinja2` dependency are gone. `print()` replaced with configured logging;
  duplicate audio function collapsed; CORS states what it does; deprecated
  `on_event` hooks became a `lifespan` handler; ports agree at 8000 across the
  Dockerfile, README and Vite proxy; zero `TODO (Chris)` markers remain;
  `backend/README.md` describes the system as it is.
- **Unit 11 — Persist `WeeklySummary`** (2026-09-07). One row per week, upserted
  on a unique `week_start_date`, holding the debrief's numbers only. Prose is
  not stored. `delivered_at` is stamped only when the email actually sends.
- **Unit 12 — Past debriefs in History** (2026-09-07). `GET /history/debriefs`
  behind an explicit response model, plus a collapsible list in History showing
  reps completed, the PR verdict, chains held with deltas, what broke and when,
  and the most avoided rep type.
- **Post-plan fixes** (2026-09-07). Sparkline chain math aligned with the
  headline number; `/history` batched from 7 queries to 2; every remaining
  hardcoded colour replaced with a token, including a named `--heat-*` ramp for
  the rhythm heatmap.
- **Backend test suite** (2026-09-07). 47 `pytest` tests over the paths
  `smoke.py` cannot reach: the chain rule, rep status transitions and the
  deletion guard, sweep windows, archiving, the first-rep rate and the debrief
  payload. Runs in ~2s against a per-session throwaway database.
- **Deploy.** Dockerfile running `alembic upgrade head || true` then uvicorn on
  port 8000, on Railway. Frontend hosted separately, pointed at the API through
  `VITE_API_URL`. CORS wide open.

- **Unit 14 — `tasks` table** (2026-09-24, branch
  `claude/project-workflow-redesign-5cg1gk`, not yet on `main`). `Task` model
  and `TaskStatus` (`pending / completed / missed / cancelled`), revision
  `8fcad7e710dc`. Additive only. Verified on a scratch Postgres 16: upgrade →
  downgrade → upgrade round-trips, and a schema dump of `reps`, `rep_types`,
  `goals` and `weekly_summaries` is identical before and after. The downgrade
  drops the `taskstatus` enum by hand, which autogenerate leaves out. 4 new
  tests (defaults, unique event id, FK, all-day), 51/51 pass; server boots and
  `smoke.py` 12/12 against the migrated database. No endpoint or UI yet.

- **Unit 15 — Pull tasks from the calendar** (2026-09-24, redesign branch).
  `GoogleCalendarClient.list_events` / `get_event`; `services/task_sync.py`
  (`parse_event` is pure, `sync_tasks` applies the six rules in its docstring);
  `GET /tasks?date=` and `POST /tasks/sync?date=`; a 15-minute `task_sync` job
  over today and tomorrow, registered only when Google is configured. Goal
  hard-delete now returns 409 while the goal has tasks, checked before any
  calendar call. Product invariant 5 and Security 3 rewritten in
  `architecture.md`; "two-way sync" left the Never list. 16 new tests with a
  fake calendar, 67/67 pass; breaking the "never rewrite a finished task" rule
  makes a test fail. Server verified against a migrated Postgres: `GET /tasks`,
  sync 503 without credentials, hard delete 409, `smoke.py` 17/17.
  **Not verified against real Google** — this container has no OAuth
  credentials. First real check: run locally with `backend/.env`, add a
  `[Goal] test` event, `POST /tasks/sync`, then delete the event and sync again.

- **Unit 16 — Check off, sweep, removal reasons** (2026-09-24, redesign
  branch). `POST /tasks/{id}/complete` (green) and
  `POST /tasks/{id}/cancel-reason`, both 409 once the task's day has ended;
  `services/task_sweep.py` and a `task_sweep` job at 00:00 `settings.tz`
  (red), registered regardless of Google config like the rep sweep. 11 new
  tests with a recording fake calendar that asserts the colours sent; 78/78
  pass, and removing the midnight check fails two of them. Verified on a
  migrated Postgres through the running server and by calling the real job
  function: completed stays completed, yesterday's pending became missed,
  cancelled untouched; `smoke.py` 17/17. Not verified against real Google.

- **Unit 17 — The daily list** (2026-09-24, redesign branch). `TodayTasks` and
  `TaskItem` at the top of Today; four `api.js` functions; `/tasks` added to
  the Vite dev proxy (without it, local dev 404s every task call). Syncs once on
  open because the backend does not record the job's last run. Verified in
  Chromium through the Vite dev server against a seeded Postgres: grouping by
  goal, all-day first, check-off turns the row green (computed colour checked),
  a reason saves and replaces its input, the not-connected note shows. Lint:
  no new errors (still the 6 pre-existing). Build passes.

- **Unit 18 — Day graph** (2026-09-24, redesign branch). `GET /tasks/graph`
  and `services/task_graph.py`; `DayGraph.jsx` on `3d-force-graph` +
  `three-spritetext` + `three` (Chris waived the explainability rule for it).
  Lazy-loaded; reached by clicking the date on Today. 2 new tests, 80/80.
  Verified in headless Chromium (SwiftShader WebGL) against a seeded Postgres:
  clusters per goal with labels, completed glowing in goal colour, missed as
  red wireframes, pending dim, drag rotates, previous day shows the empty
  state, back to Today works, no console errors. Build passes; no new lint
  errors.

- **Unit 19 — Week view by goal** (2026-09-24, redesign branch).
  `GET /tasks/graph?week_start=` (snapped to Monday); `DayGraph.jsx` renamed
  `TaskGraph.jsx` with a Day / Week switch and a ranked "Most time this week"
  list; per-goal `color_slot` so colours are stable across views. 2 new tests,
  82/82. Verified in Chromium against a seeded week: ranking and minutes
  correct (3h15 of 3h45 etc.), ties ordered by name, next week disabled on the
  current week, previous week empty state, switching back to Day, no console
  errors. Build passes; no new lint errors.

- **Unit 20 — Retire the rep UI** (2026-09-24, redesign branch). Schedule and
  Debrief tabs gone; Week and Analytics kept by Chris's choice. Today is only
  the date link and `TodayTasks`. Rep-type management removed from Goals, which
  now shows each goal's `[Title]` tag. Scheduler down to `task_sweep` and
  `task_sync` — the 23:59 rep sweep and Sunday debrief no longer run. Ten
  unused components deleted. Nav fits one row down to 360px (no horizontal
  scroll at 360/390/420/1280). 82/82 tests, `smoke.py` 17/17, build passes,
  lint down to 3 pre-existing errors (two old ones lived in deleted files).

- **Unit 21 — Goal links in the week graph** (2026-09-24, branch). Links gain
  `kind` (`task` | `shared_day`) and `weight`; `_shared_day_links` in
  `task_graph.py` links goals that both had a completed task on the same day,
  weight = shared days, week ranges only. Drawn neutral, thicker with weight,
  long and loose so clusters stay apart; hover names the days. 1 new test,
  83/83; seeded week gave exactly the expected pairs; rendered in Chromium
  with no errors.

- **Unit 22 — Installable web app** (2026-09-24, branch). Manifest, 192/512
  icons and a 180px `apple-touch-icon`, iOS meta tags, and a service worker
  with no caching and no fetch handler (a deploy can never be masked by a
  stale cache). Verified in Chromium: worker active at `/`, manifest standalone,
  icons 200. Installed on Chris's iPhone 2026-09-24.

- **Unit 23 — Push plumbing** (2026-09-24, branch). `pywebpush`;
  `push_subscriptions` table (revision `7e91a98edff9`, additive, round-trips);
  `services/push.py` (never raises, deletes 404/410 subscriptions, logs status
  only); `/push/config`, `/push/subscribe` (POST/DELETE), `/push/test`;
  `scripts/generate_vapid_keys.py`; service worker `push` and
  `notificationclick`; `PushSettings` panel on Goals with the iPhone install
  steps when not installed. 6 new tests (89/89) including one proving the
  script's keys are a matching pair. Real-crypto end-to-end against a local
  stand-in push service: decrypted payload and verified VAPID signature.
  **Live 2026-09-24:** keys generated with `python scripts/generate_vapid_keys.py`
  and added to Railway as `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and
  `VAPID_SUBJECT` (his own `mailto:`). Without them the panel says push isn't
  set up and nothing else changes. Re-generating the pair invalidates every
  subscription — the phone must re-enable notifications.
  Local note: `pywebpush` → `http-ece` does not build against this cloud
  container's Debian setuptools; tests ran in a venv (Docker upgrades
  setuptools first, so Railway is unaffected).

- **Unit 24 — The three notifications** (2026-09-24, branch).
  `services/notifications.py` (pure message builders + senders) and three
  cron jobs in `settings.tz`, registered only when push is configured:
  08:00 morning summary, 21:00 evening reminder (silent if nothing pending),
  Sunday 20:00 weekly recap (opens `/?view=week-graph`). 9 new tests, 98/98.
  Server with VAPID set logged all three next fire times in New York time;
  the week-graph launch link opens in Week mode.

## In Progress

Nothing.

## Next

**Build Plan 2** — `context/specs/14-calendar-first-redesign.md`:

14. ~~`tasks` table (schema only)~~ — shipped 2026-09-24
15. ~~Pull tasks from Google Calendar~~ — shipped 2026-09-24
16. ~~Check off, 00:00 sweep, removal reasons~~ — shipped 2026-09-24
17. ~~Today becomes the daily task checklist~~ — shipped 2026-09-24
18. ~~Day graph~~ — shipped and merged 2026-09-24
19. ~~Week view by goal~~ — shipped and merged 2026-09-24
20. ~~Retire the rep UI~~ — shipped and merged 2026-09-24

**Build Plan 1** (all shipped) — the build plan is `context/specs/00-build-plan.md` — 13 units, approved
2026-09-07. Start with **Unit 01**. In short:

1. ~~**Guard rep deletion**~~ — shipped 2026-09-07.
2. ~~**Fix chain computation**~~ — shipped 2026-09-07.
3. ~~**Render chains on Today**~~ — shipped 2026-09-07.
4. ~~**One week, one timezone**~~ — shipped 2026-09-07.
5. ~~**End-of-day sweep**~~ — shipped 2026-09-07.
6. ~~**Fix `first_rep_rate`**~~ — shipped 2026-09-07.
7. ~~**Debrief inputs**~~ — shipped 2026-09-07.
8. ~~**Debrief prompt and tone**~~ — shipped 2026-09-07.
9. ~~**Kill the N+1s**~~ — shipped 2026-09-07.
10. ~~**Calendar sync integrity**~~ · ~~11. **Persist `WeeklySummary`**~~ ·
    ~~12. **Past debriefs in History**~~ · ~~13. **Delete dead code**~~ — all
    shipped 2026-09-07.

**All thirteen units are shipped**, plus the three follow-ups the plan did not
anticipate. What remains needs decisions rather than code — see Open Questions.
The Known Violations table in `architecture.md` is now empty.

Deferred for lack of a decision, not for lack of value: push notification,
weekly-target chain rules, weekly PR scope, paused goals in the debrief,
`?hard=true`, and whether to add tests. See the plan's **Not units yet**.

## Environments — read this before trusting local data

**Local and production are different databases, not a copy.** Local
`daily_tracker` holds 176 reps dated 2023-06-19 to 2026-07-01. Production holds
320 reps starting 2026-07. Local is a dev database with old history; production
is the live system Chris uses daily.

The local `backend/.env` also carried a stale, revoked Google refresh token
until 2026-09-07, while production's was valid throughout. A local calendar test
therefore says nothing about production. Both now hold the same working token
(verified refreshing 2026-09-07).

**Both halves auto-deploy from `main`.** Railway rebuilds the API and Vercel
rebuilds the frontend on every push, so a commit is live within minutes — an API
shape change and its frontend update must ship in the same commit or production
breaks in between.

API: `daily-tracker-production-5c0a.up.railway.app` (Railway).
Frontend: `daily-tracker-xi-olive.vercel.app` (Vercel project `daily-tracker`,
scope `chris-projects-223a8ee5`). The Railway CLI
is installed and authenticated; `railway link --project Daily-tracker` connects
this directory, and `railway variables --service daily-tracker` reads config.
Changing a Railway variable triggers an automatic redeploy.

## Open Questions

The agent must not answer these on its own.

**Redesign (2026-09-24)** — all answered by Chris the same day and moved to
Decisions. None open.

**Rep system (pre-redesign)** — may be moot after Unit 20:

- **Push notification delivery.** Email with an MP3 was a stopgap; Chris still
  wants push. Which channel — a web push subscription from the dashboard, or
  something else? Blocks the readme's original Slice 4 item 17.
- **Chain rules for weekly-only rep types.** `readme.md` says a rep type with
  only a `weekly_target` chains per *week* rather than per day, and leaves the
  edge cases "TBD". Nothing in the code implements it. Blocks unit 2 above for
  any rep type without a `daily_floor`.
- **Weekly PR scope.** `get_weekly_pr` counts every completed rep across every
  goal, including archived ones. Should archived goals count toward the all-time
  PR, or does archiving a goal lower the bar?
- **Should paused goals appear in the debrief?** `readme.md` leans toward
  hiding them and never resolved it. Nothing filters on goal status today.
- **Is `?hard=true` on a goal still wanted?** It is the only path that destroys
  rep evidence. Keep as an escape hatch, or remove now that the system is in
  real use?

## Decisions

- **Calendar is the input; the tracker is the scoreboard** (2026-09-24) —
  typing work into the app and mirroring it to the calendar meant planning in
  two places, and Chris only planned in one. Tasks come from `[Goal] …` events;
  untagged events are ignored. · Traded away: Product invariant 5 ("the
  calendar is never a source") and the "never two-way sync" boundary. What is
  kept: nothing read from Google may change a completed or missed task.
- **Tasks are a new table, not reps** (2026-09-24) — tasks have no rep type,
  and fitting them into `reps` would mean making `rep_type_id` nullable, which
  rewrites a `reps` column. · Traded away: two outcome tables to read from when
  history spans both eras.
- **Unchecked at end of day = missed, event turns red** (2026-09-24) — same
  semantics as reps, so missed work stays visible.
- **"Worked more" = minutes of completed tasks** (2026-09-24) — not task count.
  · Traded away: a goal with many small wins looks lighter than one long block.
- **Keep rep history, retire the rep UI** (2026-09-24) — no rep row is deleted
  and no rep column dropped; Schedule and rep-type management leave the nav in
  Unit 20.
- **Redesign details** (2026-09-24, Chris) — primary calendar only; a task's
  duration is its calendar length, all-day events included (1440 min); tasks
  are checkable until midnight and the sweep runs at 00:00; a pending task
  whose event is deleted becomes `cancelled` and Chris writes a one-line reason
  at end of day; the Sunday debrief and chains are dropped for now. · Traded
  away: one all-day `[Goal]` event outweighs a full day of timed work in the
  graph.
- **The graph looks like Lobe Atlas** (2026-09-24) — dark, glowing points,
  coloured labelled clusters per goal, drag to rotate, scroll to zoom. Unit 18
  decides hand-written canvas vs `3d-force-graph`.
- **A goal with tasks cannot be hard-deleted** (2026-09-24, Chris) — 409,
  checked before any Google call. Task events are Chris's own and the tracker
  never deletes them; purging task rows would erase evidence. · Traded away: a
  goal created by mistake and already used in the calendar can only be
  archived.
- **An unanswered removal reason is dropped after its day** (2026-09-24,
  Chris) — "that day" is the task's own `scheduled_date`, so no new column was
  needed: the endpoint refuses a reason once that day has ended, and Unit 17's
  list shows only the day's cancelled tasks. Checking off follows the same
  midnight rule, enforced in the endpoint as well as the sweep. · Traded away:
  a reason is lost if the day ends first.
- **A pending task whose event loses its `[Goal]` prefix stays pending**
  (2026-09-24, Unit 15, agent's call within the spec) — the event still
  exists, so nothing was deleted and there is nothing to ask a reason for.
  Renaming a goal in the tracker would otherwise cancel every pending task
  tagged with its old name. · Traded away: un-tagging an event is not a way to
  withdraw a task; delete the event instead.
- **Today syncs once when it opens** (2026-09-24, Unit 17, agent's call) —
  the spec asked for a last-synced time, and the backend does not record
  when the 15-minute job ran; syncing on open makes the time real and the
  list current. · Traded away: one Google call per Today load.
- **`3d-force-graph` for the graphs** (2026-09-24, Chris) — "it's just a
  tracker project"; CLAUDE.md's "explainable by Chris" rule is waived for this
  dependency. · Traded away: a ~1.4 MB lazy chunk and a force layout nobody
  has to understand.
- **Notification times** (2026-09-24, agent default, unconfirmed) — 08:00,
  21:00, Sunday 20:00, fixed in `scheduler.NOTIFICATION_JOBS`. Change there.
- **Build Plan 3 scope** (2026-09-24, Chris) — goal lines mean "worked the
  same day" (completed tasks, week view); push notifications go to his iPhone
  as an installed web app, with all three messages: evening reminder, morning
  summary, weekly recap. Times (21:00, 08:00, Sunday 20:00) are agent
  defaults, not yet confirmed.
- **Poll the calendar, don't subscribe to push** (2026-09-24, proposed) — a
  15-minute job plus a sync button. Google watch channels need a public
  webhook, renewals and a verified domain; polling is one function Chris can
  read top to bottom.

- **First reps flagged on the six goals with real volume** (2026-09-07) — the
  flag was set on 1 of 66 rep types, so `readme.md`'s "headline behavioural
  metric" described one goal. Each goal's most-scheduled rep type is now its
  morning non-negotiable: AI and Ml Engineering (Learning and exercises, 27
  scheduled), Angle (Build project, 25), Hiclone (Build Hiclone website, 18),
  personal project (Michael Oneyze Projects, 8), Physical Exercise (push day and
  pull day, 8 each), plus Orange (Build product), already set. · Traded away:
  School and Hitwin are unmeasured, having 3 and 4 reps scheduled in total —
  not enough for a morning non-negotiable to mean anything. Applied through
  `PATCH /rep-types/{id}`; the prior state of all 43 rep types was captured
  first, so it is reversible.

- **Debrief prose is not persisted; only its numbers are** (2026-09-07) — S2
  permits an unauthenticated API precisely because the database holds rep
  metadata. A stored week-by-week narrative of what Chris works on and avoids is
  a different class of data, and Unit 12 would have made it browsable to anyone
  with the URL. · Traded away: History shows figures rather than prose, and
  rereading a past debrief in words means regenerating it, which costs an API
  call. S2 stays true as written.
- **A failed migration stops the deploy** (2026-09-07) — `|| true` dropped from
  the Dockerfile; Railway keeps serving the previous container. · Traded away: a
  broken migration now blocks a release outright, which is why `|| true` was
  added in the first place. The mitigation is verifying migrations locally — the
  scratch-database round-trip used in Unit 11 is the pattern.

- **The first-rep rate is per goal, over days a first rep was scheduled**
  (2026-09-07) — asked all-goals-at-once it is almost always zero, and counting
  every elapsed day treats "I did not plan to start early today" as a failure to
  start early. The question it answers is "of the days I planned to start early
  on this goal, how often did I?" · Traded away: the rate says nothing about how
  *often* first reps are planned. On real data last week that is the difference
  between 1/2 = 50% and 1/7 = 14%; a goal can read 100% off a single scheduled
  day, so `days_scheduled` must be displayed next to the percentage.

- **A chain survives one empty day, once, and its length is the calendar span**
  (2026-09-07) — a rep type scheduled Mon-Fri would otherwise break every
  weekend and never exceed 5, which is the "chains feel unfair, the dashboard
  feels red" V1-failure condition. One forgiven day per chain keeps a rest day
  from erasing a month of work. · Traded away: a chain reading 6 may represent
  5 completed reps, so chain length is no longer the same as reps done — the
  daily score and week total remain the honest volume measures. A second gap
  ends the run, so a daily-floor rep type cannot be held indefinitely at
  every-other-day adherence.

- **The API has no authentication, deliberately.** — Single user, single
  machine, obscure URL. · Traded away: anyone with the URL can read and write
  every goal and rep. The binding consequence is that the database may only ever
  hold rep metadata (see `architecture.md` S2). Confirmed 2026-09-07. Do not add
  auth unasked.
- **Metrics computed at read time, never stored.** — Chains and PRs are derived
  facts; storing them creates a second source of truth that can drift from
  `reps`. · Traded away: `/summary` re-runs every query on every dashboard load,
  and it is O(rep types) queries deep.
- **Calendar sync is one-way and failures are swallowed.** — The tracker must
  stay usable when Google is unreachable. · Traded away: a rep can end up with
  no calendar event and no record of the failure, which is one of the readme's
  own V1-failure conditions.
- **Reps are hard-deleted rather than soft-deleted.** — Nothing was decided
  here; `delete_rep` was written the obvious way. · This contradicts a stated
  non-negotiable and is listed as a bug, not a decision.
- **Email instead of push for the Sunday debrief.** — Push needed a service
  worker and a subscription flow; SMTP needed a Gmail app password. · Traded
  away: the debrief lands in an inbox Chris might not open on a Sunday night,
  which is the whole delivery moment. Still considered a stopgap.
- **`alembic upgrade head || true` at container start.** — Commits `024fa08`
  and `0f7664d`: the app was failing to boot on Railway when migrations
  errored. · Traded away: a failed migration now boots a running app against
  the wrong schema, silently.
- **Server-rendered Jinja dashboard abandoned for a React SPA.** — Slice 3
  wanted charts and interaction. · The Jinja router, template and stylesheet
  were left in the tree unregistered rather than deleted.
- **Third-party SDKs called synchronously inside `asyncio.to_thread`.** —
  Consistent across Google, Anthropic and `smtplib`; avoids three different
  async clients. · Traded away: a thread per external call.

## Model Corrections

- Expected three.js's bloom pass to give the Lobe Atlas glow → in headless
  Chromium it lifted the entire canvas to grey, with or without an
  `OutputPass` → replaced with additive halo sprites, which only add light;
  now assume post-processing may render differently across GPUs and prefer
  effects built from scene objects.

- Expected a merge to `main` to switch the app over in one step → Vercel
  finished the frontend minutes before Railway had built the image and run
  the migration, so the new Today called `/tasks` on the old backend and
  showed "Failed to fetch tasks" until a refresh → now assume the frontend is
  live first after any merge that adds an endpoint, and tell Chris to refresh
  once Railway's deploy completes (check `GET /<new endpoint>` directly).

- Expected the debrief payload to be JSON-serialisable → its `goals` dict was
  keyed by UUID, so `json.dumps` raised; nothing had noticed because only
  `.values()` is ever read → now assume a dict that is never serialised may not
  be serialisable, and check before Unit 11 stores it as JSONB.

- Expected `is_first_rep` to be in real use because readme.md calls first-rep
  -before-noon "the headline behavioral metric" and a non-negotiable → exactly 1
  of 66 production rep types carries the flag → now assume a documented
  non-negotiable may be unused in practice; check adoption before sizing work
  against it.
- Expected a text-slice edit bounded by a class name to be safe → the slice
  silently removed `_walk_chain`, added between those two points by Unit 02, and
  `/summary` 500ed on every request → now assume an edit anchored on line
  positions must be re-read after applying, and that booting the app is what
  catches it.

- Expected Unit 03 to be a pure wiring job because two components were already
  written → production has 53 rep types with only 7 alive, so rendering them all
  would have manufactured the "dashboard feels red" failure the readme warns
  about; the unit needed a design decision the spec never anticipated → now
  assume a spec written against local data may be wrong about scale, and check
  production volumes before implementing any list rendering.

- Expected the local database and `.env` to represent production → they are a
  separate dev environment with different data and, until 2026-09-07, a revoked
  Google token. A local `invalid_grant` and a local gap in calendar events led
  to a wrong conclusion that production sync had been dead for three months;
  production coverage was 152/172 in July and 35/35 in September → now assume
  **nothing about production can be inferred from local**; query the deployed
  API or Railway directly before making any claim about live behavior.

- Expected the weekly-target carve-out in Unit 02 to need careful handling →
  every rep type in the database has `daily_floor = 1`, so the weekly-only
  branch is dead code with no behavior to preserve → now assume a carve-out
  may be hypothetical; check the data before designing around it.
- Expected the morning-zero bug to be a theoretical edge case → replaying real
  history, the old walk reported 0 for "1h Learning" and "Build Project" on
  2026-06-30 when their chains were genuinely 2 and 3 days alive → now assume
  the dashboard has been under-reporting chains on most mornings since launch.

- Expected the local Postgres to be the live data → its reps stop at 2026-07-01
  while today is 2026-09-07, so the local database is a ~2-month-old snapshot
  and the live data is Railway's → now assume local verification runs against
  stale data, which is fine for logic but never for "is this what Chris sees".
- Expected `npm run lint` to pass, since the Definition of Done requires it →
  it reports 6 pre-existing errors on the committed tree, none in files touched
  by Unit 01 → now assume the lint gate means "introduces no new errors" until
  the existing 6 are cleared.

- Expected `/summary` to feed a dashboard that renders it → `chains` and their
  60-day histories are computed, serialized, and dropped on the floor;
  `ChainsList.jsx` and `ChainsVisualization.jsx` are imported by nothing → now
  assume a field in the API response is not evidence that anything renders it.
- Expected `get_30day_rhythm` to return 30 days → it returns the current
  calendar month, day 1 to last day → now assume function names in
  `services/summary.py` may misdescribe their behavior; read the body.
- Expected one week definition → `summary.py` uses Monday-start and
  `debrief.py` uses Sunday-start, so the Sunday debrief covers the previous
  Sun–Sat and excludes the day it runs → now assume week math is per-module
  until proven shared.
- Expected `settings.tz` to govern the scheduler because it governs everything
  else → `AsyncIOScheduler()` takes no timezone, so it resolves the *host* zone
  via `tzlocal`, and the job calls `date.today()`. Verified 2026-09-07: that
  returns `America/New_York` on the Mac and UTC in `python:3.11-slim`, so
  "Sunday 21:00" is correct in local dev and 21:00 UTC on Railway → now assume
  any timezone bug outside a request handler is invisible locally and must be
  reasoned about against the container, not the laptop.
- Expected `backend/README.md` to describe the backend → it is an unfinished
  Slice-1 TODO list telling you to open a dashboard that is no longer served →
  now assume repo docs other than `readme.md` and `context/` are stale.

## Known Debt

- **Future pending reps stay pending forever** (Unit 20, Chris's call). The
  23:59 rep sweep no longer runs, so any rep scheduled for a future day stays
  gray on the calendar and pending in the database. Delete the events in
  Google by hand if they clutter; the rows stay (never delete rep rows).
- **History draws NaN into its SVG when there is no rep history** (found in
  Unit 20 on an empty local database; History was not changed). Production
  has rep history, so it should not show there.
- **`api.js` still exports the rep endpoints** (`createRep`, `markMissed`,
  debrief calls, rep-type CRUD) that no component imports since Unit 20.
  Harmless; remove when convenient.
- **`/summary` runs its full rep aggregation only for `today_date`.** Today
  now uses nothing else from it. Cheap enough at one user; a lighter endpoint
  would do.

- **Physical Exercise runs paired rep types per weekday, not duplicates.** Two
  "push day", two "pull day" and two "Legs day", all created 2026-07-02, split
  across different days of the week — one leans Monday, the other Thursday.
  Confirmed 2026-09-07: across 12, 11 and 6 distinct scheduled days, the two
  variants of a pair have **never** landed on the same date. This was initially
  recorded as a data problem; it is deliberate. Only the higher-volume variant
  of push and pull carries `is_first_rep`, which is conservative rather than
  necessary — since a pair never collides, flagging both would widen coverage
  without any day requiring two reps before noon.

  Consolidating to one push, one pull and one legs would also merge each pair's
  chain, which is currently split across two rep types. Archiving the secondary
  alone preserves its rep rows but drops them out of chains; carrying the
  history over would mean repointing `rep_type_id` on existing reps, which
  rewrites rep rows and needs explicit approval.
- An event deleted by hand in Google Calendar leaves a stale
  `calendar_event_id`; one-way sync means the tracker cannot know. Reconciliation
  is a larger feature and is not planned.
- A reschedule while Google is unreachable moves the rep but not the event, and
  the marker cannot express it — `calendar_event_id` is still set. Logged at
  error only.


Known to be wrong and deliberately left alone for now. **Recorded so the agent
stops "helpfully" fixing them** — each becomes a unit when it is scheduled, not
when it is noticed. The full list with `file:line` is the Known Violations table
in `architecture.md`.

- `frontend/public/icons.svg` is unreferenced. Kept deliberately — `favicon.svg`
  beside it is referenced by `index.html`.
- `debrief_enabled` requires *both* `CLAUDE_API_KEY` and `ELEVENLABS_API_KEY`,
  so there is no text-only debrief even though the readme calls audio optional.
- No typecheck in CI; Ruff is configured and unused. Nothing runs `pytest`
  automatically — no CI pipeline exists, so the suite only helps when someone
  runs it.
- No frontend tests. The React components are verified by hand in a browser.
- `routers/dashboard.py` (dead, unregistered) still references the removed
  `first_rep_rate` float. Unit 13 deletes the file.
- APScheduler does not backfill a missed fire. The 23:59 sweep is immune —
  it marks everything `scheduled_date <= today`, so a skipped run is repaired by
  the next one. The Sunday debrief is not: a restart spanning 21:00 means no
  debrief that week, and nothing warns.
- `npm run lint` reports 6 pre-existing errors (`react-hooks/immutability` in
  `RepScheduling.jsx` and others). The Definition of Done says lint must pass;
  until these are cleared the practical gate is "no new errors".
- The local Postgres is a snapshot ending 2026-07-01. Live data is on Railway.
- `create_goal` enforces title uniqueness in Python with no DB constraint, so
  it is racy — harmless at one user.

## Resume Here

**Redesign in progress.** Read `context/specs/14-calendar-first-redesign.md`
first — it supersedes the notes below on direction. Units 14–16 are shipped on
`main` — all of Build Plan 2 (Units 14–20). Nothing is in flight. The open
items are the "Not units yet" list in the spec and the Known Debt below; any
new work needs a spec first.

**Local test setup in a cloud container:** `conftest.py` connects as role
`chrisilias` with no password. There, start Postgres, create that role with a
password and export `PGPASSWORD`, `PGHOST=localhost`, `PGUSER=chrisilias`
before `pytest`.

*Pre-redesign notes:*

**Read `readme.md` first — it is the original spec and still the authority on
product behavior.** Then `architecture.md`, and specifically its **Known
Violations** table: that table is the real backlog, and the Next list above is
it in priority order.

The system is deployed and in daily use, and the working tree is clean —
the OAuth script fix shipped in `9946db6`. The build plan is at `context/specs/00-build-plan.md`
and all 13 unit specs are written (`01-…` through `13-…`). The next action is
implementing Unit 01 — but four blocking questions above must be answered first:
two before Unit 02 and Unit 06 can be written correctly, two before Unit 11
ships. Unit 01 is unblocked and can start immediately.

Specs 07, 08, 09, 12 and 13 were written in a batch ahead of the units they
depend on, and each opens with a **Reconcile before implementing** section.
Read it — do not implement those from the spec alone.

The single most valuable change is the smallest: chains are already computed,
already sent to the browser, and already have two components written to render
them. Wire them into `Dashboard.jsx`, then fix the chain math behind them, and
the product finally does the thing it exists to do.
