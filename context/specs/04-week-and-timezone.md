# Unit 04: One Week, One Timezone

## Goal

Every part of the system agrees what "this week" and "now" mean. Today
`summary.py` uses a Monday-start week while `debrief.py` uses Sunday-start, and
the Sunday cron fires at 21:00 UTC in production because APScheduler was never
given `settings.tz`.

## Design

No UI. Two independent bugs sharing one root cause: time computed outside a
request handler does not use `settings.tz`.

## Implementation

### `backend/app/services/debrief.py` — week boundary

Currently:

```python
week_start = target_date - timedelta(days=target_date.weekday() + 1)  # Sunday
```

The `+ 1` makes the week Sunday-start. Combined with `week_end = week_start + 7`
and a `>= week_start, < week_end` filter, the Sunday 21:00 debrief reports on
the *previous* Sunday through Saturday and **excludes the day it runs**.

Change to Monday-start, matching `summary.py` exactly:

```python
week_start = target_date - timedelta(days=target_date.weekday())
```

`readme.md` declares Mon–Sun; `summary.py` is the correct one. Both now derive
the week identically, so the debrief covers the week the dashboard has been
showing all week.

### `backend/app/scheduler.py` — timezone

Two changes:

1. `AsyncIOScheduler()` → `AsyncIOScheduler(timezone=settings.tz)`.
2. `today = date.today()` → `today = datetime.now(tz=settings.tz).date()`.

**Why this is invisible locally.** APScheduler with no `timezone=` resolves the
host zone through `tzlocal`. Verified 2026-09-03: that returns
`America/New_York` on Chris's Mac and UTC inside `python:3.11-slim`. So the cron
is correct in dev and fires five hours early on Railway. The same applies to
`date.today()`.

Consider extracting the shared week-start calculation into one helper both
services import, so the two cannot drift apart again. Keep it in
`services/summary.py` and import it from `debrief.py` — service-to-service
imports are permitted; a router importing it would not be.

## Verifying a production-only bug

This unit **cannot be verified on the laptop by running it**, because the
laptop's zone happens to be the correct one. Two checks instead:

1. Run the app with `TZ=UTC` set, simulating the container, and assert the job's
   next fire time is 21:00 America/New_York — not 21:00 UTC. Log
   `scheduler.get_job("weekly_debrief").next_run_time` at startup and read it.
2. After deploying, confirm the next fire time in the Railway logs before the
   following Sunday rather than waiting to see whether the email is late.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| Container has no `TZ` set | Scheduler now uses `settings.tz` regardless | Debrief arrives 21:00 ET |
| `APP_TIMEZONE` is an invalid zone name | `ZoneInfo` raises at import of `settings.tz` — fails fast at boot | App does not start; Railway shows the error |
| DST transition on a debrief Sunday | `ZoneInfo` handles the offset shift | Debrief arrives at local 21:00 either side of the change |
| Job overruns past midnight | The week was captured at job start, so the report stays internally consistent | Correct week reported |
| Scheduler misses a fire (restart, sleep) | APScheduler default is to skip, not backfill | No debrief that week; nothing warns |

That last row is pre-existing and not fixed here — note it in
`progress-tracker.md` under Known Debt rather than widening this unit.

## Threat Model

- **Data handled:** dates and a timezone name from configuration. No user input.
- **Who can access it:** not reachable over HTTP — this is startup and job code.
- **Attacker controls the input:** `APP_TIMEZONE` comes from the environment. An
  attacker who can set env vars already owns the process; `ZoneInfo` rejects a
  malformed value at boot rather than silently defaulting.
- **Storage breached:** not applicable.

## Dependencies

None. APScheduler and `zoneinfo` are already present.

## Verify when done

**Technical**
- [ ] `debrief.py` and `summary.py` produce identical `week_start` for the same date, verified across a Sunday and a Monday
- [ ] The Sunday debrief includes reps completed on the Sunday it runs
- [ ] With `TZ=UTC` set, the job's `next_run_time` is 21:00 America/New_York
- [ ] No `date.today()` or naive `datetime.now()` remains in `scheduler.py`
- [ ] App boots clean

**Security**
- [ ] Threat model run against the implementation
- [ ] An invalid `APP_TIMEZONE` fails at boot rather than silently falling back to UTC

**Product**
- [ ] Technical invariant 4 (`settings.tz` everywhere) holds outside request handlers
- [ ] Remove both timezone/week rows from Known Violations in `architecture.md`
- [ ] Add the "missed fire is not backfilled" note to Known Debt
