# Unit 02: Fix Chain Computation

## Goal

`get_chains` returns a chain length that is correct before the day's rep is
done, excludes archived rep types, and includes rep types that have never been
completed. Chains are the psychological core of the product and currently every
one of them reads 0 every morning.

## Design

Backend only — no UI in this unit. Unit 03 renders the result.

## Implementation

### `backend/app/services/summary.py` — `get_chains`

Four defects in one function (currently lines ~110-150).

**1. The walk starts on the wrong day.** Today:

```python
current_day = today
while current_day in dates_completed:
```

A chain held every day through yesterday reads 0 until today's rep is checked
off, because the loop never enters. Anchor the walk to today when today has a
completion, and to yesterday when it does not:

```python
anchor = today if today in dates_completed else today - timedelta(days=1)
current_day = anchor
while current_day in dates_completed:
    chain_length += 1
    current_day -= timedelta(days=1)
```

A chain last completed two or more days ago still correctly yields 0.

**2. Archived rep types are included.** `select(RepType)` has no status filter.
Add `.where(RepType.status == RepTypeStatus.active)`, so a paused domain stops
occupying the dashboard.

**3. Rep types with no completions vanish.** `if not completed_reps: continue`
hides them entirely, so a newly created rep type does not appear until its first
completion. Remove the `continue` and emit a `ChainInfo` with `current_chain=0`
and `last_completed_date=None`. A chain at zero is information; an absent row is
not.

**4. `daily_floor` is not consulted.** Per `readme.md`, a chain breaks when a
day passes with zero completions **and** that rep type has a daily floor above
zero. So `daily_floor` decides *whether the type chains daily at all*, not how
many completions a day needs — the chain definition is explicitly "at least one
rep of that type was completed". Compute a daily chain only for rep types with
`daily_floor` set and greater than 0. **Do not** treat `daily_floor = 3` as
requiring three completions; that reading is not in the spec.

### Carve-out: weekly-only rep types

Rep types with `daily_floor` null and only a `weekly_target` chain **per week**
per `readme.md`, whose edge cases it leaves explicitly TBD. That is an
unresolved open question. **Leave their current behavior unchanged and do not
guess a weekly rule.** Emit them as they are computed today, and note in the
code which branch is awaiting a decision.

## Open Question — resolve before implementing

**Does an unscheduled day break a chain?** `readme.md`'s literal rule is "a
chain breaks when a day passes with zero completions of that rep type". Taken
literally, a rep type scheduled Monday to Friday breaks its chain every Saturday
and can never exceed 5. That may be the intent — or it may produce exactly the
"chains feel unfair, the dashboard feels red" outcome listed as a V1-failure
condition.

Three readings, none of which should be chosen by the agent:

1. **Literal** — any day with zero completions breaks it. Weekends break
   weekday-only rep types.
2. **Scheduled days only** — a day with no rep of that type scheduled is
   skipped rather than breaking the chain.
3. **Floor-aware** — only days on or after the rep type's creation, and only
   days its cadence actually calls for, count.

This changes the number on the dashboard, so it needs an answer before the walk
is written.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| Rep type with zero completions | Emitted at chain 0 with `last_completed_date` null | A chain row reading 0 |
| Rep type created today, completed today | Chain of 1 | 1 |
| All rep types archived | Empty list, not an error | Chains empty state (Unit 03) |
| Clock crosses midnight mid-request | `today` is read once per call; the response is internally consistent | Possible off-by-one for one request at midnight; self-corrects on refetch |
| Database unreachable | Exception propagates as a 500 from `/summary` | "Failed to fetch summary" |

## Threat Model

- **Data handled:** `reps` and `rep_types` rows, read-only. No writes.
- **Who can access it:** anyone with the API URL, per S2. Unchanged.
- **Attacker controls the input:** the only input is `settings.tz` and the
  request's optional `date`, both already parsed. No user-supplied string
  reaches a query.
- **Storage breached:** unchanged; this unit adds no storage.

## Dependencies

None.

## Verify when done

**Technical**
- [ ] A rep type completed yesterday but not today reports its true chain length, not 0
- [ ] Completing today's rep increments it by exactly 1
- [ ] A rep type last completed two days ago reports 0
- [ ] Archived rep types are absent from the response
- [ ] A rep type with no completions appears at chain 0
- [ ] Weekly-only rep types behave exactly as before this unit
- [ ] Verified against a hand-counted real rep type, not only synthetic rows

**Security**
- [ ] Threat model run against the implementation
- [ ] No raw SQL introduced

**Product**
- [ ] The open question above was answered by Chris and the answer recorded in `progress-tracker.md` under Decisions
- [ ] Product invariant 4 (independent chains) still holds — no rep type's chain can affect another's
- [ ] Remove the chain-math row from Known Violations in `architecture.md`
