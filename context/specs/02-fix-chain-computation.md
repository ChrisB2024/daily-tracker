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

## The chain rule — decided 2026-09-07

A single empty day is forgiven **once per chain**. A second gap, or any gap of
two or more days, breaks it. Chain length is the **calendar span** from the
first to the last completed day of the run, inclusive — so the forgiven rest day
counts toward the number.

Today is never judged: it has not finished yet, so a missing completion today
neither breaks a chain nor spends the grace.

### Worked examples

```
Mon ✓  Tue ✓  Wed ✓   (today Wed)          -> 3
Mon ✓  Tue —  Wed ✓   (today Wed)          -> 3   gap forgiven, span Mon..Wed
Mon ✓  Tue ✓  Wed ·   (today Wed, not done)-> 2   today not judged, no reset
Mon ✓  Tue —  Wed ·   (today Wed, not done)-> 1   grace covers Tue
Mon ✓  Tue —  Wed —  Thu ·                 -> 0   two elapsed empty days
Mon ✓  Tue —  Wed ✓  Thu —  Fri ✓ (today)  -> 3   second gap ends it at Wed
```

### Algorithm

```
last = max(dates_completed)                  # 0 if the set is empty
days_since = (today - last).days
if days_since > 2: chain = 0                 # two or more elapsed empty days
grace_used = (days_since == 2)               # yesterday was the forgiven day

start = last
cur   = last - 1 day
loop:
    if cur completed:                start = cur;      cur -= 1 day
    elif not grace_used and (cur - 1 day) completed:
                       grace_used = True;  start = cur - 1 day;  cur -= 2 days
    else: break

chain = (last - start).days + 1
```

`days_since <= 2` is what keeps a live chain from reading 0 in the morning, and
it is deliberately separate from the grace rule: an unfinished today is not a
gap, whereas an empty yesterday is.

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
