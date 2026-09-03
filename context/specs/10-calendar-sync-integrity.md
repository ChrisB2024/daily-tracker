# Unit 10: Calendar Sync Integrity

## Goal

The calendar can no longer silently stop mirroring the tracker. A failed event
creation is recorded and visible instead of being swallowed, and rescheduling a
rep moves its calendar event. "Calendar sync lags or silently fails" is a listed
V1-failure condition, and both holes are live.

## Design

A rep whose calendar event is missing needs to be visible as such. Since
`RepRead` already exposes `calendar_event_id`, the frontend can detect
`calendar_event_id === null` on a rep that should have one and mark the row.

Use a small muted indicator on the row — not an error color. `--missed` means
"you did not do this" and must keep that meaning; a sync failure is a system
problem, not a behavioral one. Use `--muted` with a title attribute explaining
the rep is not on the calendar.

**No schema change.** Adding a `calendar_sync_failed` column would make this the
first migration since `alembic upgrade head || true` entered the Dockerfile, and
that decision belongs to Unit 11. A null `calendar_event_id` already carries the
signal.

## Implementation

### `services/google_calendar.py` — surface failures

`create_event`'s handler catches everything, logs at `warning`, and returns
`None`. Callers assign that straight onto `rep.calendar_event_id`, so a failure
is indistinguishable from success.

Keep the swallow — Technical invariant 5 says a third-party call must never
raise into a handler — but make it loud and legible:

- Log at `error`, not `warning`, with the rep id.
- Have callers in `create_rep` and `create_reps_bulk` check for `None` and log
  explicitly that the rep was persisted without a calendar event.

Do not add a retry loop inside the request. A retry against an unreachable
Google turns a fast create into a slow one, and the rep is already safely
stored.

### `services/google_calendar.py` — a time patch

Add `patch_time(event_id, start_dt, end_dt, tz)` alongside `patch_color`,
following the same structure: build the service, `events().patch(...)`,
try/except, log, `asyncio.to_thread`.

### `routers/reps.py` — `update_rep` re-syncs

`update_rep` writes new `scheduled_date`, `scheduled_time` or `duration_minutes`
and never touches the calendar, so the event stays at the old time forever —
Product invariant 5 (the calendar is a mirror) broken by the tracker itself.

After committing, if any of those three fields changed and
`rep.calendar_event_id` is set, recompute start and end and call `patch_time`.
Compare against the pre-update values to avoid patching on an unrelated edit
such as `notes`.

### Frontend

In `RepItem`, when a rep has no `calendar_event_id`, render the muted indicator
with an explanatory `title`. `TodayReps` and `WeekView` inherit it.

`RepInSummary` in `routers/summary.py` does **not** currently include
`calendar_event_id`, so `/summary` cannot express this. Add the field to that
response model — an additive change, safe for the existing client.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| Google down at create | Rep saved, no event, logged at error | The rep with an "not on calendar" marker |
| Google down at reschedule | Rep moves in the tracker, event stays put, logged at error | Marker cannot express this — **known limitation**, since `calendar_event_id` is still set. Log it and note in Known Debt. |
| Refresh token revoked | Every operation fails and is logged | Every new rep marked unsynced — the pattern makes the cause obvious |
| Only `notes` edited | No calendar call | Nothing |
| Event deleted in Google by hand | Patch fails, logged, `calendar_event_id` still set | Stale id; one-way sync means the tracker cannot know. Out of scope — reconciliation is a bigger feature. |
| Duration changed only | End time patched, start unchanged | Event resizes |

## Threat Model

- **Data handled:** `calendar_event_id`, rep times, and the Google OAuth
  credentials used to patch. Rep type names, goal titles and notes already
  travel to Google at create time; this unit adds no new field to that payload.
- **Who can access it:** `PATCH /reps/{id}` is open per S2, so anyone with the
  URL can move a rep and cause a calendar write. That was already true; this
  unit makes the write actually happen.
- **Attacker controls the input:** dates, times and durations are parsed by
  Pydantic. An absurd `duration_minutes` produces an absurd event, not a crash —
  consider whether a sane bound belongs here or in the schema, and if so add it
  to `RepUpdate` rather than the router.
- **Storage breached:** unchanged. The refresh token remains in the environment,
  never in Postgres, so a database compromise still yields no calendar access.

## Dependencies

None. Independent of every other unit; sequenced here because it is lower value
than the chain and debrief work, not because it is blocked.

## Verify when done

**Technical**
- [ ] A create with Google unreachable persists the rep, logs at error, and leaves `calendar_event_id` null
- [ ] The unsynced marker renders on such a rep in Today and Week
- [ ] Changing a rep's date or time moves the calendar event
- [ ] Changing only `notes` triggers no calendar call
- [ ] Changing duration resizes the event
- [ ] `calendar_event_id` present in `RepInSummary`; existing client unaffected
- [ ] `npm run lint` passes

**Security**
- [ ] Threat model run against the implementation
- [ ] No credential or token in any new log line
- [ ] Technical invariant 5 still holds — no third-party exception reaches a handler

**Product**
- [ ] Product invariant 5 (calendar is a mirror) holds for create, complete, miss, reschedule and delete
- [ ] The unsynced marker uses `--muted`, never `--missed`
- [ ] Remove both calendar rows from Known Violations in `architecture.md`
