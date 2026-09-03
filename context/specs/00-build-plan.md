# Build Plan

Approved 2026-09-03. Units in build order, each producing one visible result.

This is not a greenfield plan — the system is deployed and in daily use. Every
unit below closes a gap between what the system promises and what it does. The
source of truth for those gaps is the **Known Violations** table in
`context/architecture.md`; when a unit lands, remove the row it fixes.

**Subsystems.** The value engine is rep tracking, chains and the debrief. The
experience layer is the Today dashboard. Trust infrastructure here is **not**
authentication — that is deliberately absent (see `architecture.md` S2) — it is
**the rep evidence trail**. That reading is what pulls Unit 01 to the front:
the system's integrity claim is that missed reps survive, and today one click
destroys them.

---

## Unit 01 — Guard rep deletion

**Builds:** `DELETE /reps/{id}` returns 409 for any rep that is not `pending`.
The ✕ disappears from completed and missed rows in Today and Week.
**Depends on:** nothing
**Boundary:** API route + UI — deliberately crossed, see note
**Subsystem:** trust infrastructure

Restores the "missed reps stay visible" non-negotiable. Currently
`reps.py:151` hard-deletes any rep in any status, and `RepItem.jsx:20-26`
renders the button on every row.

*Boundary note:* this breaks the one-boundary rule on purpose. A backend guard
alone leaves a button that throws an `alert()`, which is worse than the bug.
Land and verify the 409 first, then remove the button.

**Done when:** deleting a pending rep still works and removes its calendar
event · deleting a completed or missed rep returns 409 · no ✕ renders on a
non-pending row.

---

## Unit 02 — Fix chain computation

**Builds:** `get_chains` returns a chain length that is correct in the morning.
**Depends on:** nothing
**Boundary:** service layer (`services/summary.py`)
**Subsystem:** value engine

Four defects in one function (`summary.py:130-134`): the walk starts at
`today`, so a chain alive through yesterday reads 0 until today's rep is done;
`daily_floor` and `weekly_target` are ignored; `select(RepType)` has no status
filter so archived types keep appearing; `if not completed_reps: continue`
hides any rep type that has never been completed.

*Scope carve-out:* covers `daily_floor` rep types only. Rep types with only a
`weekly_target` chain per week per `readme.md`, whose edge cases are an
unresolved open question — leave their behavior unchanged and do not guess.

**Done when:** a chain completed yesterday but not yet today reads its true
length, not 0 · archived rep types are absent · a rep type with zero
completions appears at chain 0 rather than vanishing · weekly-only rep types
are untouched.

---

## Unit 03 — Render chains on Today

**Builds:** chains visible on the dashboard.
**Depends on:** Unit 02
**Boundary:** UI (`Dashboard.jsx`)
**Subsystem:** experience layer

`/summary` already computes chains and a 60-day history for each, serializes
them, and `Dashboard.jsx` imports neither `ChainsList.jsx` nor
`ChainsVisualization.jsx`. Both components are already written. This is the
smallest change with the largest product effect in the whole plan.

*Ordering note:* after 02 on purpose. "Chains feel unfair" is a stated
V1-failure condition — rendering a chain that wrongly reads 0 is worse than
rendering none.

**Done when:** per-rep-type chains render on Today · charts use `var(--…)`
rather than the hardcoded hex the existing SVGs use · the empty state reads as
a real state when no chains exist.

---

## Unit 04 — One week, one timezone

**Builds:** every part of the system agrees what "this week" and "now" mean.
**Depends on:** nothing
**Boundary:** service layer + scheduler
**Subsystem:** value engine

Two independent bugs with one root: time is computed differently outside
request handlers. `debrief.py:26` uses a Sunday-start week while
`summary.py` uses Monday-start, so the Sunday debrief covers the *previous*
Sun–Sat and excludes the day it runs. `AsyncIOScheduler()` gets no timezone and
the job calls `date.today()`.

*Verified 2026-09-03:* APScheduler resolves the host zone via `tzlocal`, which
returns `America/New_York` on the Mac and UTC in `python:3.11-slim` — so the
cron is correct in local dev and fires at 21:00 UTC on Railway. **This unit
cannot be verified on the laptop alone.**

**Done when:** `debrief.py` uses Monday-start · `AsyncIOScheduler(timezone=settings.tz)` ·
`datetime.now(tz=settings.tz).date()` replaces `date.today()` · the next Sunday
debrief arrives at 21:00 America/New_York.

---

## Unit 05 — End-of-day sweep

**Builds:** unfinished reps turn red without anyone pressing a button.
**Depends on:** Unit 04
**Boundary:** scheduler + API route
**Subsystem:** value engine

A 23:59 job in `settings.tz` marking that day's still-pending reps missed and
patching their calendar events red. Also fixes the manual sweep, which filters
`scheduled_date <= today_date` (`reps.py:196`) and therefore kills today's
pending reps when pressed at 09:00.

*Depends on 04* because a 23:59 job inherits the same timezone bug — build it
on a scheduler that already knows what time it is.

**Done when:** the cron marks only `scheduled_date == today` · the manual
endpoint uses `< today` · both patch calendar events to red · pressing the
dashboard button mid-morning no longer touches today's reps.

---

## Unit 06 — Fix `first_rep_rate`

**Builds:** a first-rep rate that measures behavior instead of intent.
**Depends on:** nothing
**Boundary:** service layer
**Subsystem:** value engine

`summary.py:56-90` filters `scheduled_time < time(12,0)` — the time the rep was
*scheduled*, not completed. It always divides by 7, so Monday caps at 14%. It
requires every first-rep type across every goal including paused and archived
ones, and returns `0.0` when none exist.

*Open question, do not guess:* whether the metric is all-goals-at-once or
per-goal. With three active goals each holding a first rep, the current
all-or-nothing reading is almost always zero. Resolve before implementing.

**Done when:** the rate keys off `completed_at < noon` in `settings.tz` ·
divides by elapsed days in the week, not 7 · excludes archived and paused
goals · the headline metric matches a hand-count for a real week.

---

## Unit 07 — Debrief inputs

**Builds:** `get_weekly_summary_data` returns everything the debrief is
supposed to talk about.
**Depends on:** Units 02, 04, 06
**Boundary:** service layer
**Subsystem:** value engine

Currently the debrief sees completed/missed/pending per goal and a completion
rate — steps 2 through 4 of `readme.md`'s pipeline are absent. Add: per-rep-type
chain length and its change vs last week, week total against the all-time PR,
first-rep rate, broken chains and when they broke, most-completed and
most-avoided rep type.

*This is where the dependency chain pays off* — the debrief cannot be right
until chain math (02), the week definition (04) and the first-rep rate (06) are.

**Done when:** the returned payload carries all of the above · the numbers match
what the dashboard shows for the same week.

---

## Unit 08 — Debrief prompt and tone

**Builds:** a debrief that reads like findings.
**Depends on:** Unit 07
**Boundary:** service layer
**Subsystem:** value engine

`debrief.py:100` asks Claude for a "personal coach… encouraging… motivating"
summary. `readme.md` forbids exactly that: no motivational quotes, no emoji, no
praise — chains, numbers, patterns. "The Sunday debrief feels generic" is a
stated V1-failure condition. Move the model to `claude-opus-5` while here.

*Kept separate from 07* because its verification is qualitative — read the
output and judge whether it sounds like a friend who has been watching. That is
a different kind of check from "the payload has the fields", and worth isolating.

**Done when:** the prompt asks for quantified findings and forbids praise ·
model is `claude-opus-5` · a generated debrief for a real week names chain
lengths, the PR comparison and the most-avoided rep type, and contains no
encouragement.

---

## Unit 09 — Kill the N+1s

**Builds:** a dashboard load that does not scale with the number of rep types.
**Depends on:** Units 02, 06, 07
**Boundary:** service layer
**Subsystem:** —

Zero `selectinload`/`joinedload` in the repo; 13 `session.refresh(...)` calls
inside loops; `get_summary` runs a chain query *plus* a 60-day history query per
rep type; counts use `len(result.scalars().all())`;
`GoogleCalendarClient._build_service` refreshes OAuth on every operation and
`create_reps_bulk` builds a fresh client per rep, so scheduling 14 reps performs
14 serial token refreshes. `backend/README.md` itself says to use `selectinload`.

*Deliberately late* — it rewrites the same functions 02, 06 and 07 touch. Doing
it first means writing those queries twice.

**Done when:** no `session.refresh` inside a loop · counts use
`select(func.count())` · one `GoogleCalendarClient` per bulk request · `/summary`
returns identical JSON to before, measurably faster.

---

## Unit 10 — Calendar sync integrity

**Builds:** a calendar that cannot silently stop mirroring the tracker.
**Depends on:** nothing
**Boundary:** service layer + API route
**Subsystem:** trust infrastructure

Two holes. `create_event` returns `None` on failure (`google_calendar.py:110`)
and callers assign it to `rep.calendar_event_id` unchecked, so a rep ends up
permanently unsynced with no record and no retry. `update_rep`
(`reps.py:126-141`) changes `scheduled_date`/`scheduled_time` without patching
the event, so the mirror drifts. "Calendar sync lags or silently fails" is a
stated V1-failure condition.

**Done when:** a failed event creation is recorded and visible rather than
swallowed · rescheduling a rep moves its calendar event · the invariant that a
third-party call never raises into a handler still holds.

---

## Unit 11 — Persist `WeeklySummary`

**Builds:** debriefs that survive being generated.
**Depends on:** Unit 08
**Boundary:** schema (model + migration) + service layer
**Subsystem:** value engine

`readme.md` specifies a `WeeklySummary` table; none exists, so debriefs are
ephemeral and History cannot show past ones. Model, Alembic revision, and a
write on generation.

*Depends on 08* so what gets persisted is the good debrief, not the
encouraging one.

*Decision required before this ships:* this is the first new migration since
`alembic upgrade head || true` was added to the Dockerfile (commits `024fa08`,
`0f7664d`). A failed migration currently boots the app against the old schema
silently. Keep the `|| true` and verify locally, or let a bad migration fail
the deploy loudly?

**Done when:** the migration applies cleanly against a real Postgres · a
generated debrief is stored with its week, stats, text and audio reference · no
existing rep data is touched.

---

## Unit 12 — Past debriefs in History

**Builds:** History renders stored debriefs.
**Depends on:** Unit 11
**Boundary:** UI + API route
**Subsystem:** experience layer

**Done when:** past weeks are listable · a stored debrief renders its text and
plays its audio · the empty state is real for a week with no stored debrief.

---

## Unit 13 — Delete dead code

**Builds:** a repo where nothing lies about what it does.
**Depends on:** nothing
**Boundary:** repo-wide
**Subsystem:** —

The unregistered Jinja dashboard (`routers/dashboard.py`, `templates/`,
`static/`); `backend/README.md`, which is a completed Slice-1 TODO list telling
you to open a dashboard that is no longer served; `print()` → `logging` in
`scheduler.py`, `email.py`, `debrief.py`; stale `# TODO (Chris):` comments on
implemented columns plus the `models/task.py` reference in `alembic/env.py`; the
duplicate `generate_debrief_audio_bytes` / `generate_debrief_audio` pair;
`EXPOSE 8080` against a process binding 8000; the Vite proxy pointing at 8001
while the docs say 8000.

*Last on purpose* — it touches many files and would collide with every unit
above.

**Done when:** the app boots and every view works with the dead code gone ·
`backend/README.md` describes the system as it is · no `print()` remains in a
service or the scheduler.

---

## Not units yet

- **Push notification for the Sunday debrief.** Email with an MP3 was a
  stopgap and push is still wanted, but the channel is an open question — web
  push from the dashboard, or something else? Blocks `readme.md` Slice 4 item 17.
- **Weekly-target chain rules.** Carved out of Unit 02. `readme.md` says a
  weekly-only rep type chains per week and leaves the edge cases TBD.
- **Weekly PR scope.** `get_weekly_pr` counts completed reps across every goal
  including archived ones. Should archiving a goal lower the all-time bar?
- **Paused goals in the debrief.** `readme.md` leans toward hiding them and
  never resolved it. Nothing filters on goal status today.
- **`?hard=true` on goals.** The only path that destroys rep evidence. Keep as
  an escape hatch, or remove now the system is in real use?
- **Tests, typecheck, CI.** None exist; Ruff is configured and unwired.
  Verification is currently manual against a running server. Its own decision,
  not a side effect of another unit.
