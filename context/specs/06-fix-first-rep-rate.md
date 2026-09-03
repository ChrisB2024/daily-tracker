# Unit 06: Fix `first_rep_rate`

## Goal

The first-rep-before-noon rate measures what Chris actually did, not what he
scheduled. It currently filters on `scheduled_time`, always divides by 7, and
counts archived and paused work.

## Design

No UI change. `FirstRepStrip` already renders `rate` as a percentage bar and
needs no edit — the number behind it becomes true.

## Blocking Open Question — answer before implementing

**Is the metric all-goals-at-once, or per goal?**

`readme.md` defines it as "the percentage of days where every rep type flagged
`is_first_rep = true` was completed before noon". With three active goals each
holding a first rep, that all-or-nothing reading is almost always zero, which
makes the headline behavioral metric useless.

Options, none to be chosen by the agent:

1. **All goals, all-or-nothing** — literal reading. One missed first rep zeroes
   the day.
2. **All goals, proportional** — the day scores the fraction of first reps
   completed before noon, and the week averages those.
3. **Per goal** — a rate per goal, displayed per goal. Changes the API shape
   and `FirstRepStrip`, which would push UI work into this unit or a follow-up.

This determines both the arithmetic and whether the response shape changes, so
it must be settled first.

## Implementation

### `backend/app/services/summary.py` — `get_first_rep_rate`

**1. Measure completion, not intent.** The filter is currently
`Rep.scheduled_time < time(12, 0)` — the time the rep was *scheduled*. Use
`completed_at` instead.

`completed_at` is `DateTime(timezone=True)`, written as
`datetime.now(tz=settings.tz)`. Extracting a local time-of-day from a
`timestamptz` in SQL requires an explicit `AT TIME ZONE` conversion; getting it
wrong silently shifts the noon boundary by hours. **Fetch the candidate rows and
compare in Python** — `rep.completed_at.astimezone(tz).time() < time(12, 0)` —
which is unambiguous and, at one user's volume, costs nothing. Note the choice
in a comment so it is not "optimized" into a fragile SQL expression later.

**2. Stop dividing by 7.** The denominator is elapsed days in the week, not 7,
so Monday can read 100% rather than capping at 14%. Denominator is
`min(today, week_end) - week_start + 1` days.

Decide and record what an unscheduled day means: if no first rep was scheduled
on a day, does that day count against the rate? Treating it as a miss punishes a
deliberate rest day. This is the same shape of question as Unit 02's — resolve
it alongside that one and record both in `progress-tracker.md`.

**3. Exclude archived and paused work.** The query selects every
`is_first_rep` rep type regardless of `RepType.status`, and regardless of its
goal's status. Filter to `RepType.status == active` joined to goals with
`GoalStatus.active`.

**4. The empty case.** It returns `0.0` when no first-rep types exist, which
renders as a 0% bar and reads as failure rather than "not applicable". Return a
value the UI can distinguish — `None`, with `FirstRepStrip` rendering a real
empty state — or keep 0.0 and accept the misreading. Prefer the former; it costs
one conditional and matches the "never a blank or lying state" rule in
`ui-context.md`.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| No first-rep types defined | Returns `None` (or 0.0 — see above) | An explicit "no first reps defined" state, not 0% |
| A first rep completed at 11:59 local | Counts | Rate includes the day |
| Completed at 12:00:00 exactly | Does not count — the boundary is strictly before noon | Rate excludes the day |
| `completed_at` null on a completed rep (legacy row) | Treated as not-before-noon rather than crashing | Day does not count; no error |
| A rep completed in a different DST offset | `astimezone` resolves correctly per date | Correct |
| Every first-rep type archived | Same as none defined | Empty state |

## Threat Model

- **Data handled:** `reps.completed_at`, `rep_types.is_first_rep`, and goal
  status. Read-only.
- **Who can access it:** anyone with the URL, per S2. Unchanged.
- **Attacker controls the input:** only the optional `date` query parameter,
  already parsed by FastAPI into a `date`. No string reaches a query.
- **Storage breached:** unchanged.

## Dependencies

None in packages. Unit 07 depends on this, so it should land before the debrief
rewrite.

## Verify when done

**Technical**
- [ ] The blocking question above is answered and the answer recorded under Decisions
- [ ] A first rep completed at 11:00 counts; one completed at 13:00 does not, even when scheduled for 09:00
- [ ] On a Monday with the first rep done, the rate reads 100%, not 14%
- [ ] Archived rep types and paused or archived goals are excluded
- [ ] A legacy completed rep with null `completed_at` does not raise
- [ ] Hand-verified against one real week

**Security**
- [ ] Threat model run against the implementation
- [ ] No `AT TIME ZONE` string built from user input

**Product**
- [ ] The rate is a behavioral measure — it changes when Chris changes *when he
      works*, not when he changes *when he schedules*
- [ ] Remove the `first_rep_rate` row from Known Violations in `architecture.md`
- [ ] Chris confirms the number matches his sense of the week. **What surprised you?**
