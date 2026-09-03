# Unit 09: Kill the N+1s

## Goal

A dashboard load stops issuing a query per rep type, and bulk-scheduling stops
performing one OAuth token refresh per rep. `/summary` must return byte-identical
JSON afterwards — this unit changes how the data is fetched, never what it says.

## Reconcile before implementing

Written before Units 02, 06 and 07, which rewrite the same functions. **Re-read
`get_chains`, `get_first_rep_rate` and `get_weekly_summary_data` as they now
stand.** Some N+1s named below may already be gone, and new ones may have
appeared. Capture a baseline first: log the query count and wall time for one
`/summary` call against real data, so "measurably faster" is a number rather
than an impression.

## Design

No UI, no behavior change. Pure mechanical work behind an unchanged contract.

## Implementation

### Relationship loading

Thirteen `await session.refresh(obj, ["rep_type", "goal"])` calls sit inside
loops, and the repo contains no `selectinload` or `joinedload` at all —
`backend/README.md` itself says to use `selectinload` "to avoid lazy-load
explosions". Replace each with eager loading on the `select()`:

```python
select(Rep).where(...).options(selectinload(Rep.rep_type), selectinload(Rep.goal))
```

Sites: `get_today_reps`, `get_week_reps` (a loop inside a loop over seven days),
`get_chains` (refreshes the goal per rep type), `get_rep_type_analytics`, and
`get_weekly_summary_data`.

### Counting

`get_daily_score` and `get_week_total` do `len(result.scalars().all())` — every
matching row is loaded from Postgres to be counted. Use
`select(func.count()).select_from(Rep).where(...)`.

`get_weekly_pr` loads every completed rep in history and groups them in Python.
Group by week in SQL with `date_trunc` and take the max. Verify the week
boundary matches the Monday-start rule Unit 04 settled — a `date_trunc('week')`
in Postgres is Monday-based, which agrees, but confirm rather than assume.

### The summary fan-out

`routers/summary.py` calls `get_chain_history` once per chain and
`get_goal_progression` once per goal, each of which runs its own query. With ten
rep types that is ten extra round trips per dashboard load. Fetch the reps for
the whole window once and bucket them in Python, or batch the queries with an
`IN` clause.

### Calendar client

`GoogleCalendarClient._build_service` calls `credentials.refresh(Request())` on
every operation, and `create_reps_bulk` constructs a fresh client per rep — so
scheduling fourteen reps performs fourteen serial token refreshes and fourteen
service builds. Two changes:

1. Build the client once per request and reuse it across the loop.
2. Cache the built service on the instance so repeated operations reuse one
   refresh. Keep it per-instance, not module-global: a long-lived cached
   credential is a token that outlives the request that needed it.

## Non-goals

Do not add caching, a read replica, background precomputation, or a materialized
metrics table. Metrics are computed at read time by design (Technical invariant
2) and this unit does not revisit that.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| An eager load changes result ordering | Rows arrive in a different order and the UI shifts | Caught by the byte-identical JSON check below |
| `date_trunc` week disagrees with the app's Monday-start | PR silently changes value | Caught by comparing PR before and after against real data |
| A cached calendar service outlives its access token | The next call fails with an auth error, swallowed and logged | A rep silently unsynced — refresh on expiry rather than caching indefinitely |
| Batched query grows past parameter limits | Postgres errors on a very large `IN` | Not reachable at one user's volume; chunk if it ever is |
| A refactor drops a filter | Wrong numbers, quietly | The identical-JSON check is the guard; do not skip it |

## Threat Model

- **Data handled:** the same rows as before, fetched differently. No new data,
  no new endpoint.
- **Who can access it:** unchanged, per S2.
- **Attacker controls the input:** unchanged. Batched queries must be built with
  bound parameters through SQLAlchemy — **no f-string or string-concatenated
  `IN` list**, which is the one way this unit could introduce an injection where
  none existed.
- **Storage breached:** unchanged. The cached OAuth service holds an access
  token in process memory for the life of a request; it must not be written
  anywhere or shared across requests.

## Dependencies

- Units 02, 06 and 07 complete. Running this first means writing those queries
  twice.

## Verify when done

**Technical**
- [ ] `/summary` returns byte-identical JSON to the pre-change response for the same date and data
- [ ] Baseline and post-change query count and wall time recorded in `progress-tracker.md`
- [ ] No `session.refresh` remains inside a loop
- [ ] Counts use `select(func.count())`
- [ ] `get_weekly_pr` returns the same value as before against real data
- [ ] Bulk-scheduling 14 reps performs one token refresh, not 14
- [ ] All 14 events still appear in the calendar

**Security**
- [ ] Threat model run against the implementation
- [ ] No raw SQL or string-built query introduced; every batch uses bound parameters
- [ ] No credential cached beyond the request that built it

**Product**
- [ ] Technical invariant 2 intact — nothing precomputed or stored
- [ ] Dashboard numbers unchanged, verified against a real week
- [ ] Remove the efficiency row from Known Violations in `architecture.md`
