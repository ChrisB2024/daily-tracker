# Working Rules

Direct instructions to the agent. These are rules, not preferences.

## Operating Mode

Build against specs, one unit at a time. The context files define what to
build, how it must fit together, and where the work currently stands. Implement
what is specified — do not infer product behavior that is not written down.

**This is a live system in daily use.** It is deployed on Railway and Chris
opens it every morning. A broken deploy costs him the day's tracking, and lost
rep data cannot be reconstructed. Prefer a small verified change over a
sweeping one.

## Scope Discipline

- One unit at a time. Finish it before starting the next.
- Never combine unrelated system boundaries in a single step.
- Do not refactor code the current unit did not touch. This repo has a long
  Known Violations list in `architecture.md` and a long debt list in
  `progress-tracker.md` — **they are inventory, not a to-do list for the
  current unit.** Fixing one that the spec did not name is out of scope.
- Do not install a dependency until the unit that needs it.
- Do not migrate the frontend to TypeScript, add a router, add a state library,
  or add a test framework as a side effect of another unit. Each is its own
  decision and none has been made.

## Split the Work If

- It changes the schema *and* the UI. The migration lands and is verified first.
- It touches both the metric layer (`services/summary.py`) and the debrief
  pipeline (`services/debrief.py`). They share a week definition and disagree
  about it today; fix that in its own unit.
- It changes rep status transitions *and* the calendar sync path.
- Part of it is not clearly defined in the context files.

If the result cannot be verified end to end in one sitting, the scope is too
wide. Split it.

## Missing or Ambiguous Requirements

- Never invent product behavior. A plausible guess is still a guess.
- `readme.md` is the original spec and is the tiebreaker on product intent —
  but it is stale on scope (see `project-overview.md` Boundaries). Where code
  and readme disagree on *behavior*, the readme wins and the code is a bug.
  Where they disagree on *what features exist*, the code wins.
- If a requirement is ambiguous, resolve it in the context file first, then
  implement.
- If a requirement is absent, log it under Open Questions in
  `progress-tracker.md` and ask before proceeding.

## Data and Deploy Safety

- **Never write a migration that drops or rewrites a column on `reps`** without
  saying so explicitly and getting a yes. The rep history is the product.
- Never delete rep rows in a script or a fix. `?hard=true` on a goal is the only
  sanctioned destructive path and only Chris triggers it.
- The container runs `alembic upgrade head || true` at start, so a broken
  migration boots a running app against an old schema instead of failing loudly.
  Verify a migration locally against Postgres before it ships.
- Never commit `backend/.env` or echo its contents into output.

## When a Correction Fails Twice

Two failed corrections on the same item is a hard stop. There is no third
attempt.

1. Stop editing. Do not revert the failed attempts — the diff is evidence.
2. Compare the two failures. **Different** failures mean the spec is ambiguous.
   **Identical** failures mean the model of the code is wrong.
3. Verify the diverging assumption by running an actual check — a query against
   the real database, a log line, a request to the endpoint. Never by reasoning
   about what the code probably does. This codebase has several functions whose
   names misdescribe their behavior (`get_30day_rhythm` returns a calendar
   month); read the body, do not trust the name.
4. Report: the failing `file:line`, the exact spec sentence it was meant to
   satisfy, expected vs actual for each attempt, and the single question that
   needs answering.
5. Fix the source. Ambiguity fixes the spec; contradiction fixes the context
   file. Then revert and implement once, cleanly.

Never patch around a blockage while leaving the spec wrong.

## Explainability

Chris is learning backend development by building this system. Everything that
ships must be explainable by him. If he would stumble explaining it, it is not
ready.

**Scaffold first.** Produce structure and TODOs where he intends to write the
logic himself, and ask which parts he wants to own before writing a large block
of implementation. This is his stated working preference, and the existing
models still carry the `# TODO (Chris):` comments from it. When reviewing his
code, report real bugs and architectural problems — not style nits.

## Protected Files

Do not modify without explicit instruction:

- `backend/alembic/versions/*` — both revisions are applied.
- `backend/.env` — real secrets.
- `frontend/package-lock.json`, `backend/daily_tracker.egg-info/`.
- `backend/app/routers/dashboard.py`, `backend/app/templates/`,
  `backend/app/static/` — dead server-rendered dashboard, removal is a tracked
  unit.

## Keep the Docs True

Update the relevant context file *before* continuing whenever implementation
changes:

- A system boundary or ownership rule
- The storage model
- An invariant, or the way one is enforced
- A convention other code will be expected to follow
- Feature scope

When a unit fixes something in `architecture.md`'s **Known Violations** table,
remove that row in the same change. When a unit reveals a new violation, add one.

## Definition of Done

All three layers pass, or the unit is not done.

**Technical**
1. Works end to end within the unit's stated scope.
2. Invalid and hostile input handled without crashing.
3. `uvicorn app.main:app --reload` boots clean; the touched endpoints return
   expected shapes against a real Postgres. There is no test suite and no
   typecheck in CI — **manual verification against a running server and a real
   database is the bar**, and it must actually be run, not assumed.
4. `npm run lint` passes for frontend changes.

**Security**
5. No secret reachable from a response, a log line, or the client bundle.
6. Nothing new stored in Postgres beyond rep metadata.
7. Google OAuth scope unchanged.

**Product**
8. No invariant in `architecture.md` was violated, and no Known Violation was
   copied as precedent.
9. Calendar state still mirrors tracker state for every path the unit touched.
10. `progress-tracker.md` reflects the finished work.

A failure in any layer sends the unit back to planning. That is the process
working, not a setback.
