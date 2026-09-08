# Unit 05: End-of-Day Sweep

## Goal

Reps left pending at the end of the day are marked missed and turn red in the
calendar automatically at 23:59, without Chris pressing anything. The manual
sweep stops marking *today's* still-pending reps as missed when pressed in the
morning.

## Design

No new UI. The dashboard's "Run end-of-day sweep" button stays as a manual
override, but its meaning changes: it sweeps days that have already ended, never
the current day.

## Implementation

### Extract the sweep into the service layer

The logic currently lives inline in `routers/reps.py:mark_missed`, which
violates the ownership rule that routers do not compute. Move it to
`services/summary.py` (or a new `services/sweep.py` if it reads better there) as
a function taking an explicit date window, so the cron and the endpoint share
one implementation and cannot drift.

```python
async def sweep_missed(session, *, through: date, include_through: bool) -> int
```

Returns the number of rows updated. Keeps the existing single bulk `UPDATE` —
do not convert it to a Python loop.

### The window rule — revised 2026-09-07

`mark_missed` filters `Rep.scheduled_date <= today_date`, so pressing the button
at 09:00 marks today's still-pending reps missed.

Both callers want the same thing — *sweep every day that has ended* — and differ
only in whether today counts as ended. So one function, one window:

```
sweep_missed(session, *, through: date) -> int
    marks every pending rep with scheduled_date <= through as missed
```

- **23:59 cron** — `through = today`. The day is over, so today counts.
- **Manual endpoint** — `through = today - 1 day`. Today is still open, so
  pressing the button at any hour cannot touch it.

The original spec said the cron should sweep `scheduled_date == today` exactly.
That is wrong: APScheduler does not backfill a missed fire (logged as debt while
building Unit 04), so a restart spanning 23:59 would strand that day's reps as
`pending` forever, invisible to both the sweep and the user. `<= through` is
self-healing and, at 23:59, cannot mark anything early — every day it touches
has genuinely ended.

### The cron job

In `scheduler.py`, register a second job alongside the debrief:

```python
scheduler.add_job(
    sweep_missed_job, "cron", hour=23, minute=59,
    id="end_of_day_sweep", replace_existing=True,
)
```

The scheduler already carries `timezone=settings.tz` after Unit 04 — **this unit
depends on that**, or the sweep fires at 23:59 UTC and marks the wrong day.

`init_scheduler` currently returns early when email is not configured, which
would also disable this job. Restructure so the sweep is registered
unconditionally and only the debrief job is gated on `settings.email_enabled`.

### Sessions in jobs

The existing debrief job builds its own engine per run. The new job should use
`AsyncSessionLocal` from `app.db.session` instead. Do not refactor the debrief
job's engine handling here — that is noise for this unit; log it as debt.

### Calendar colors

Reuse the existing pattern: collect `calendar_event_id` values for the rows
about to change, run the bulk update, then patch each event to `colorId` 11.
Build **one** `GoogleCalendarClient` for the batch, not one per event — the
per-rep client construction is a known defect and must not be copied here.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| No pending reps for the day | Update affects 0 rows; no calendar calls | Nothing changes |
| Google Calendar unreachable | Statuses still change; `patch_color` swallows and logs per event | Reps show missed in the app, still gray in the calendar. **The mirror silently drifts** — accepted here, addressed in Unit 10. |
| A rep is completed at 23:58:59 | It is no longer `pending`, so the filter skips it | Stays green |
| Job overruns past midnight | The date is captured once at job start | The correct day is swept |
| App restarts across 23:59 | APScheduler does not backfill a missed fire | Those reps stay pending until the next manual sweep |
| Manual sweep pressed at 09:00 | Only days before today are swept | Today's reps untouched — the bug this unit fixes |
| Calendar patches are slow | The job blocks on serial `to_thread` calls | No user-visible effect; it is a background job |

## Threat Model

- **Data handled:** `reps.status` and `calendar_event_id` for one day.
- **Who can access it:** the cron runs unauthenticated inside the process. The
  manual endpoint is open to anyone with the URL, per S2 — unchanged, but note
  its blast radius is now *smaller*, since it can no longer affect the current
  day.
- **Attacker controls the input:** the manual endpoint takes no parameters. An
  attacker can force a sweep of already-ended days, which is idempotent — every
  affected rep was going to be swept anyway.
- **Storage breached:** unchanged.

## Dependencies

- Unit 04 must be complete. A 23:59 job on a scheduler with the wrong timezone
  sweeps the wrong day and is worse than no job at all.

## Verify when done

**Technical**
- [ ] A pending rep dated today is `missed` and red shortly after 23:59 local
- [ ] A pending rep dated today is untouched by the manual endpoint at any hour
- [ ] A pending rep dated yesterday is swept by the manual endpoint
- [ ] Completed reps are never touched by either path
- [ ] The endpoint still returns the affected row count
- [ ] The sweep job registers even when email is not configured
- [ ] One `GoogleCalendarClient` per sweep, not one per event
- [ ] `next_run_time` for `end_of_day_sweep` reads 23:59 America/New_York under `TZ=UTC`

**Security**
- [ ] Threat model run against the implementation
- [ ] The endpoint remains parameterless — no client-supplied date window

**Product**
- [ ] `project-overview.md` "Done Looks Like" item 3 now holds without manual action
- [ ] Rep state machine still allows only `pending → missed`
- [ ] Remove both sweep rows from Known Violations in `architecture.md`
