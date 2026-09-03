# Progress

Update after every meaningful change. This file is how a cold session recovers
full context in one read.

Reconstructed on 2026-09-03 from the code, `readme.md`'s build order, and git
history. Nothing here was verified against a running instance — the state of
the live Railway deploy is recorded as Chris reported it.

## Phase

**Shipped and in daily use.** All five slices from `readme.md`'s build order
have landed in some form. Chris confirmed on 2026-09-03 that the Railway
backend and hosted frontend are up and he uses it every day.

The work now is not "finish V1" — it is closing the gap between what the system
promises and what it actually does. Three of the readme's own V1-failure
conditions are currently live: the debrief reads as encouragement, calendar sync
can fail silently, and chains display wrong (in fact, not at all).

## Working On

Nothing in flight. The only uncommitted change is
`backend/scripts/google_oauth.py`, which switches the one-time OAuth flow to
`127.0.0.1` with `open_browser=False` and exits non-zero when Google returns no
refresh token. It looks finished and is unreleased — **decide whether to commit
it before starting anything else.**

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
- **Deploy.** Dockerfile running `alembic upgrade head || true` then uvicorn on
  port 8000, on Railway. Frontend hosted separately, pointed at the API through
  `VITE_API_URL`. CORS wide open.

## In Progress

Nothing.

## Next

No build plan exists yet — run `/six-file-context plan` to produce
`context/specs/00-build-plan.md`. Based on the reconciliation in
`architecture.md`, the ordering that follows is:

1. **Render chains on the Today view.** Wire the already-written `ChainsList` /
   `ChainsVisualization` into `Dashboard.jsx`. Highest value per line changed —
   the data is already computed and serialized.
2. **Fix chain computation.** Start the walk from yesterday when today has no
   completion yet; honour `daily_floor` and `weekly_target`; filter archived rep
   types; include rep types with zero completions at chain 0. Do this with (1)
   or immediately after — rendering a wrong chain is worse than rendering none.
3. **One week definition.** Make `debrief.py` use Monday-start like
   `summary.py`, and give the scheduler `settings.tz` so the Sunday job fires at
   21:00 America/New_York instead of 21:00 UTC.
4. **Automatic end-of-day sweep** at 23:59 in `settings.tz`, and fix the manual
   sweep's `scheduled_date <= today` window so pressing it at 09:00 stops
   killing today's pending reps.
5. **Rewrite the debrief prompt and its inputs** — findings not encouragement,
   and feed it chains, PR comparison, first-rep rate, and most-avoided rep type,
   per `readme.md`'s pipeline steps 2–4.
6. **Stop hard-deleting reps.** Guard `DELETE /reps/{id}` to `pending` only, and
   remove the ✕ from completed and missed rows.
7. **Fix `first_rep_rate`** to measure `completed_at < noon`, divide by elapsed
   days, and ignore archived and paused goals.
8. **Kill the N+1s** — `selectinload` instead of `refresh`-in-a-loop,
   `select(func.count())` instead of `len(...all())`, one `GoogleCalendarClient`
   per bulk request instead of one per rep.
9. **Persist `WeeklySummary`** so History can show past debriefs.
10. **Delete the dead server-rendered dashboard** and rewrite
    `backend/README.md`, which is a completed Slice-1 TODO list.

## Open Questions

The agent must not answer these on its own.

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
- **First-rep semantics.** `readme.md`'s metric is "days where every rep type
  flagged `is_first_rep` was completed before noon". Across *all* goals at once,
  or per goal? With three active goals each having a first rep, the current
  all-or-nothing reading makes the metric almost always zero.
- **Should paused goals appear in the debrief?** `readme.md` leans toward
  hiding them and never resolved it. Nothing filters on goal status today.
- **Is `?hard=true` on a goal still wanted?** It is the only path that destroys
  rep evidence. Keep as an escape hatch, or remove now that the system is in
  real use?

## Decisions

- **The API has no authentication, deliberately.** — Single user, single
  machine, obscure URL. · Traded away: anyone with the URL can read and write
  every goal and rep. The binding consequence is that the database may only ever
  hold rep metadata (see `architecture.md` S2). Confirmed 2026-09-03. Do not add
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
  via `tzlocal`, and the job calls `date.today()`. Verified 2026-09-03: that
  returns `America/New_York` on the Mac and UTC in `python:3.11-slim`, so
  "Sunday 21:00" is correct in local dev and 21:00 UTC on Railway → now assume
  any timezone bug outside a request handler is invisible locally and must be
  reasoned about against the container, not the laptop.
- Expected `backend/README.md` to describe the backend → it is an unfinished
  Slice-1 TODO list telling you to open a dashboard that is no longer served →
  now assume repo docs other than `readme.md` and `context/` are stale.

## Known Debt

Known to be wrong and deliberately left alone for now. **Recorded so the agent
stops "helpfully" fixing them** — each becomes a unit when it is scheduled, not
when it is noticed. The full list with `file:line` is the Known Violations table
in `architecture.md`.

- Stale `# TODO (Chris):` comments on already-implemented columns throughout
  `backend/app/models/rep_type.py`, plus an unanswered TODO question in
  `config.py` and a reference to a nonexistent `models/task.py` in
  `alembic/env.py`.
- `backend/README.md` is a completed TODO list.
- Dead server-rendered dashboard: `routers/dashboard.py`, `templates/`,
  `static/`.
- Dead frontend components: `ChainsList.jsx`, `ChainsVisualization.jsx` (dead
  only until unit 1 wires them in), and unreferenced `public/icons.svg`.
- `print()` instead of `logging` in `scheduler.py`, `email.py`, `debrief.py`.
- Duplicate near-identical functions `generate_debrief_audio_bytes` and
  `generate_debrief_audio` in `services/debrief.py`.
- `debrief_enabled` requires *both* `CLAUDE_API_KEY` and `ELEVENLABS_API_KEY`,
  so there is no text-only debrief even though the readme calls audio optional.
- SVG charts hardcode hex instead of using CSS custom properties.
- `@app.on_event("startup")` is deprecated in favour of a lifespan handler.
- `Dockerfile` declares `EXPOSE 8080` while the process binds 8000.
- Vite dev proxy targets `localhost:8001`; `backend/README.md` and the
  Dockerfile both say 8000.
- No test suite, no typecheck in CI. Ruff is configured and unused.
- `create_goal` enforces title uniqueness in Python with no DB constraint, so
  it is racy — harmless at one user.

## Resume Here

**Read `readme.md` first — it is the original spec and still the authority on
product behavior.** Then `architecture.md`, and specifically its **Known
Violations** table: that table is the real backlog, and the Next list above is
it in priority order.

The system is deployed and in daily use. The one uncommitted change is
`backend/scripts/google_oauth.py`; decide whether to commit it before starting.
There is no build plan yet — run `/six-file-context plan` to create one.

The single most valuable change is the smallest: chains are already computed,
already sent to the browser, and already have two components written to render
them. Wire them into `Dashboard.jsx`, then fix the chain math behind them, and
the product finally does the thing it exists to do.
