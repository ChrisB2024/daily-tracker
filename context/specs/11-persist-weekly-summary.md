# Unit 11: Persist `WeeklySummary`

## Goal

A generated debrief survives being generated. `readme.md` specifies a
`WeeklySummary` table; none exists, so every debrief is thrown away the moment
it is read and History cannot show past ones.

## Blocking Decision — settle before this ships

**Should a failed migration keep booting the app?**

This is the first new migration since `alembic upgrade head || true` entered the
Dockerfile (commits `024fa08`, `0f7664d`, added because migrations were failing
the Railway deploy). Today a broken migration boots a running app against the old
schema, silently — the app then serves 500s from any code path touching the new
table, with a green deploy.

Two options:

1. **Keep `|| true`** and verify every migration against a real Postgres locally
   before pushing. Deploys never hard-fail; the cost is that a schema mismatch
   is discovered through errors rather than a failed deploy.
2. **Drop `|| true`** so a bad migration fails the deploy loudly and the
   previous container keeps serving.

This is Chris's call and it affects how this unit is shipped, not just this
unit's code.

## Secondary Decision — where does audio live?

`readme.md`'s model has `audio_url`, which implies external storage. There is no
object store, and `architecture.md`'s storage model explicitly forbids blobs in
Postgres.

Default taken by this spec unless Chris says otherwise: **store text and stats,
leave `audio_url` null, and regenerate audio on demand.** It respects the
storage rule, needs no new infrastructure, and audio is described as optional in
`readme.md`. Introducing object storage to persist an MP3 nobody has asked to
replay is a larger decision than this unit.

## Design

Backend and schema only. Unit 12 renders these records; this unit stores them.

## Implementation

### `backend/app/models/weekly_summary.py`

Per `readme.md`'s data model, following the conventions in the existing three
models — UUID primary key defaulting to `uuid4`, `Mapped[]` columns,
`server_default=func.now()` on `created_at`:

- `id` — UUID, primary key
- `week_start_date` — `Date`, not null, indexed. Monday-start, per Unit 04.
- `rep_data` — JSON. Per-rep-type stats: chain length, counts, PR comparison.
- `patterns` — JSON. Avoided and dominant rep types, first-rep rate.
- `text_summary` — `Text`, not null
- `audio_url` — `Text`, nullable. Null for now, per the decision above.
- `delivered_at` — `DateTime(timezone=True)`, nullable. Set when the email
  actually sends, distinguishing "generated" from "delivered".
- `created_at` — `DateTime(timezone=True)`, server default

Use `sqlalchemy.dialects.postgresql.JSONB` rather than generic `JSON` — this is
a Postgres-only application and JSONB is the better column type.

Register it in `models/__init__.py`. It has no relationships; it is a snapshot,
not a live view.

**Uniqueness:** one summary per week, or a history of regenerations? A unique
index on `week_start_date` gives idempotence — regenerating overwrites. Without
it, `GET /debrief` writes a new row on every page load, which is likely not
wanted. Prefer the unique index with an upsert on regeneration, and record the
choice.

### Migration

`alembic revision --autogenerate -m "add weekly_summary"`, then **read the
generated SQL before applying it**. Autogenerate must produce exactly one
`create_table` and its index — if it proposes dropping or altering anything on
`goals`, `rep_types` or `reps`, stop and investigate. Never let a migration
touch `reps`.

### Writing the record

In `services/debrief.py`, after text generation succeeds, upsert the row. The
scheduler's job sets `delivered_at` once `send_debrief_email` returns true.

**Persist only a successful debrief.** Unit 08 returns a fixed failure sentence
when Anthropic is unreachable; storing that as the week's permanent record would
be worse than storing nothing.

## Failure Modes

| Scenario | Behavior | What the user sees |
| -------- | -------- | ------------------ |
| Migration fails on deploy | Depends on the blocking decision above | Either a failed deploy, or a running app 500ing on debrief routes |
| Debrief regenerated for the same week | Upsert replaces the row | One record per week |
| Anthropic failed; text is the fixed failure sentence | Nothing persisted | No row for that week; regenerating later still works |
| Email fails after a successful generation | Row stored, `delivered_at` stays null | The debrief is retrievable even though the email never arrived — the point of this unit |
| Two writes race for one week | Unique index rejects the second | Handle the conflict as an update, not a 500 |
| `rep_data` shape changes in a later unit | Old rows carry the old shape | Unit 12 must tolerate both, or the payload needs a version field. **Consider adding one now** — it is free today and expensive later. |

## Threat Model

- **Data handled:** a persisted behavioral profile — chains, completion rates,
  which work Chris avoids, in prose. This is materially more sensitive than
  anything the database has held so far, all of which was reconstructible
  metadata.
- **Who can access it:** everything in this database is reachable by anyone with
  the API URL, per S2. **This unit is the first real test of Security invariant
  2**, which permits only rep metadata precisely because the API is open. A
  stored narrative about Chris's work habits is arguably past that line.
  Flag it and get an explicit ruling: either S2 is amended to cover it, or the
  summary text stays out of the database and only the structured stats are
  stored.
- **Attacker controls the input:** `rep_data` and `patterns` are
  application-generated; `text_summary` is model output. Nothing user-supplied
  is stored raw. Render it as text in Unit 12 — never as HTML.
- **Storage breached:** a reader gains a week-by-week account of what Chris
  worked on and avoided. No credentials, no tokens — the refresh token remains
  in the environment.

## Dependencies

- Unit 08 complete, so what gets persisted is the good debrief rather than the
  encouraging one.
- No new packages. JSONB ships with SQLAlchemy's Postgres dialect.

## Verify when done

**Technical**
- [ ] Both blocking decisions above are answered and recorded under Decisions
- [ ] Generated migration reviewed line by line; it creates one table and touches no existing one
- [ ] Migration applies cleanly against a real Postgres, and `downgrade` reverses it
- [ ] Generating a debrief stores exactly one row for that week
- [ ] Regenerating the same week updates rather than duplicating
- [ ] A failed generation stores nothing
- [ ] `delivered_at` is set only after the email actually sends
- [ ] No existing rep, rep type or goal row is modified

**Security**
- [ ] Threat model run against the implementation, and the S2 question above answered explicitly
- [ ] No secret or credential in the stored payload
- [ ] Model output stored as text, never interpreted

**Product**
- [ ] `architecture.md` storage model updated — the "nowhere" entry for debriefs is no longer accurate
- [ ] Entity lifecycle table gains a `WeeklySummary` row: created by, modified by, ends how
- [ ] Remove the `WeeklySummary` row from Known Violations
