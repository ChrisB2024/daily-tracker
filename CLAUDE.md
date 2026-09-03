# Daily Tracker

Single-user, goal-driven rep tracker. Domain is **Goal → RepType → Rep**.
Deployed on Railway and in daily use — treat it as a live system.

## Project Context

Read these before implementing anything or making any architectural decision:

1. `context/project-overview.md` — the problem, the core flow, scope
   boundaries, and what done looks like
2. `context/architecture.md` — stack, ownership map, data flow, trust
   boundaries, the invariants that must never break, and the **Known
   Violations** table (this is the real backlog)
3. `context/ui-context.md` — tokens, layout patterns, required states, and
   feedback behavior
4. `context/code-standards.md` — domain vocabulary, conventions, security
   rules, and coupling rules
5. `context/ai-workflow-rules.md` — how to scope, split, verify, and when to stop
6. `context/progress-tracker.md` — where the work stands, what was decided and
   why, and what is still open

Then read the spec for the unit being built, in `context/specs/`.

`readme.md` is the original spec and remains the authority on **product
behavior** — where the code contradicts it, the code is a bug. It is stale on
**scope**: features it lists as out of scope have shipped. `context/` reflects
the current state.

## Rules

Implement what is specified. Do not invent product behavior that is not written
down — if something is missing or ambiguous, ask, or log it under Open Questions
in `context/progress-tracker.md`.

The Known Violations and Known Debt lists are **inventory, not a to-do list**.
Fixing something the current unit did not name is out of scope.

Chris is learning backend development by building this. Scaffold structure and
TODOs where he wants to write the logic himself, and ask before writing a large
block of implementation. Everything that ships must be explainable by him.

Never delete rep rows, and never write a migration that drops or rewrites a
column on `reps` without explicit approval. The rep history is the product.

There is no test suite and no CI typecheck. Verification means running the
server against a real Postgres and checking the endpoints you touched.

Update `context/progress-tracker.md` after every meaningful change.

If implementation changes an invariant, a boundary, the storage model, scope,
or a convention, update the relevant context file before continuing. When a
unit fixes a row in the Known Violations table, remove that row in the same
change.
