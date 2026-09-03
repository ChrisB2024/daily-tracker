# Unit 07: Debrief Inputs

## Goal

`get_weekly_summary_data` returns everything the Sunday debrief is supposed to
talk about: chains and how they moved, week total against the all-time PR, the
first-rep rate, which chains broke and when, and the most-completed and
most-avoided rep types. Today it returns completed/missed/pending per goal and a
completion rate — steps 2 through 4 of `readme.md`'s pipeline are simply absent.

## Reconcile before implementing

This spec was written in a batch, before Units 02, 04 and 06 were built. Those
three units change the exact functions this one consumes. **Before writing code,
re-read `get_chains`, `get_weekly_pr` and `get_first_rep_rate` as they now
exist** and reconcile:

- Did Unit 02's open question resolve so that an unscheduled day breaks a chain?
  That decides whether "broken chains this week" is a meaningful list or noise.
- Did Unit 06 change the first-rep return type to `None` for "not applicable"?
  If so this payload must carry that distinction through, not coerce it to 0.
- Did Unit 02 change `ChainInfo`'s shape?

If any answer differs from what is assumed below, fix this spec first, then
implement.

## Design

Backend only. Unit 08 consumes this payload; no prompt or tone work here. The
split is deliberate: this unit is mechanical and checkable ("does the dict have
the fields"), while Unit 08 is a judgment call about how the output reads.

## Implementation

### `backend/app/services/debrief.py` — `get_weekly_summary_data`

Keep the existing per-goal completed/missed/pending counts and completion rate.
Add, reusing `services/summary.py` rather than reimplementing — service-to-service
imports are permitted and duplicate week math is what caused Unit 04:

**Per rep type**
- Current chain length, from `get_chains`.
- Change versus the same measure a week earlier, so the debrief can say "up
  two" rather than only "six".
- Reps completed this week against the rep type's `weekly_target` or
  `daily_floor` expectation.
- The dates of missed reps.

**Week totals**
- Total completed this week (`get_week_total`).
- The all-time PR (`get_weekly_pr`) and whether this week beat, matched or fell
  short of it.
- First-rep rate (`get_first_rep_rate`).

**Patterns**
- Longest chain currently held.
- Chains that broke during the week, and the date each broke.
- Most-completed rep type.
- Most-avoided rep type across all goals — the one with the worst
  completed-against-expected ratio, not merely the lowest raw count, or a
  rarely-scheduled rep type will always win.

### Scope boundaries

- **Do not** send rep `notes` to Anthropic. Security invariant 4 permits
  aggregates and goal titles to leave the system; raw rep content may not.
- **Do not** change the prompt, the model, or the response shape of
  `GET /debrief` beyond adding fields to `stats`.
- Paused goals: whether they appear in the debrief is an open question in
  `progress-tracker.md`. **Do not decide it here** — carry current behavior
  forward and leave a comment marking the branch.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| A week with zero reps | Every aggregate returns a zero or empty value; no division by zero | A debrief that correctly reports an empty week |
| No prior week to compare against | Chain delta is null, not 0 — "no comparison" differs from "no change" | Debrief omits the comparison |
| No PR yet (first week ever) | PR equals this week; the comparison is suppressed | No PR claim made |
| A rep type with neither floor nor target | Expectation is null; it is excluded from the avoidance ranking rather than scoring infinitely bad | Not named as most-avoided |
| One aggregate query raises | The whole debrief fails rather than reporting partial numbers | "Failed to fetch debrief" — correct, since a debrief with silently missing sections is worse than none |
| Many rep types | More queries; this runs weekly in a background job | No user-visible latency |

That last row interacts with Unit 09 — do not pre-optimize here; Unit 09 owns it.

## Threat Model

- **Data handled:** aggregated rep counts, chain lengths, rep type names and
  goal titles. Explicitly **not** rep notes.
- **Who can access it:** `GET /debrief` is open to anyone with the URL, per S2.
  This unit meaningfully increases what that endpoint discloses — from counts to
  a behavioral profile. Accepted under S2, but worth stating plainly rather than
  discovering later.
- **Attacker controls the input:** the `date` query parameter, already parsed to
  a `date`. A caller can request any week; there is nothing to protect beyond
  what the dashboard already shows.
- **Storage breached:** this unit stores nothing. Unit 11 changes that, and its
  threat model must revisit exactly this payload.

## Dependencies

- Units 02, 04 and 06 complete and verified. This unit is where the dependency
  chain pays off: the debrief cannot be correct until chain math, the week
  definition and the first-rep rate are.

## Verify when done

**Technical**
- [ ] The payload carries chains with deltas, week total, PR comparison, first-rep rate, broken chains with dates, most-completed and most-avoided rep type
- [ ] Every number matches what the dashboard shows for the same week
- [ ] A week with zero reps produces a valid payload, no exception
- [ ] Chain delta is null, not 0, when no prior week exists
- [ ] No rep `notes` value appears anywhere in the payload

**Security**
- [ ] Threat model run against the implementation
- [ ] Security invariant 4 holds — aggregates and titles only

**Product**
- [ ] The payload contains every input `readme.md`'s pipeline steps 2-4 call for
- [ ] Paused-goal behavior is unchanged and the open question still stands
- [ ] Remove the debrief-content row from Known Violations in `architecture.md`
