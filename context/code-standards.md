# Code Standards

The conventions actually in force, recovered from the code on 2026-09-07. Where
two patterns compete, the chosen one is stated and the other is logged as
cleanup in `progress-tracker.md`.

## Security — non-negotiable

Adapted to what this system is: a single-user tool with a deliberately
unauthenticated API (see `architecture.md` Security invariant S2).

1. **Authentication** — there is none, by decision. Do not add it unasked. The
   consequence is binding: **never store anything in Postgres whose disclosure
   would matter.** No credentials, no third-party tokens, no sensitive content
   in `Rep.notes`.
2. **Authorization** — not applicable; one user owns every row. Never write
   code that *implies* multi-user ownership (a `user_id` column, an owner check)
   without the feature being asked for.
3. **Input validation** — every request body and every path/query parameter is
   a Pydantic model or an annotated FastAPI parameter. No handler reads raw
   `Request` data. Cross-entity constraints that the database cannot express
   (`rep_type.goal_id == payload.goal_id`) are asserted in the route before the
   insert.
4. **Secrets** — read only through `app.config.settings`. Never a bare
   `os.environ` read, never a literal in code, never in a log line, never in a
   response body. `backend/.env` stays gitignored.
5. **Transport** — Railway terminates TLS. Gmail SMTP uses STARTTLS on 587.
   Google and Anthropic SDKs are HTTPS by default.
6. **Dependencies** — floor-pinned (`>=`) in `pyproject.toml`, caret-ranged in
   `package.json`. Add a dependency only in the unit that needs it.

## Boundaries and Coupling

- The import direction is one-way: `models` ← `schemas` ← `routers` → `services`
  → `models`. **A service never imports a router. A model never imports
  anything from the app but `db.base`.**
- Third-party SDKs are reachable only from `app/services/`. A router that wants
  Google Calendar imports `GoogleCalendarClient`; it never touches
  `googleapiclient`.
- Metric computation lives in `app/services/summary.py` and nowhere else.
  A router may call several of its functions and assemble the response; it may
  not compute.
- Frontend: every HTTP call lives in `frontend/src/api.js`, one exported
  function per endpoint. A component that needs data imports from `../api`. **No
  component contains a URL or a `fetch`.**
- Shared state: there is none. `Dashboard.jsx` owns view selection and the
  summary payload; every other view fetches its own data and owns it. Do not
  introduce a store.

## Naming

- **Domain vocabulary — use these words, never a synonym.** A **Goal** is an
  outcome. A **RepType** is a named binary unit of work belonging to one goal,
  defined by its **criterion**. A **Rep** is one scheduled instance of a rep
  type. A **chain** is a per-rep-type consecutive-day streak — never "streak"
  in code. **Daily score** is completed reps on a date; **week total** is
  completed reps in the Mon–Sun week; **PR** is the best-ever week total.
  **First rep** is a rep type flagged `is_first_rep`. Never write "task",
  "habit", or "todo" — the readme rejects all three deliberately.
- Python: `snake_case` functions and columns, `PascalCase` models, schemas and
  enums. Service functions read as their output: `get_daily_score`,
  `get_chains`, `get_weekly_pr`.
- Schemas are three per resource: `XCreate`, `XUpdate`, `XRead`. Response-only
  models nested in a router file are named `…InSummary` (`RepInSummary`,
  `ChainInSummary`).
- JS: `camelCase` functions, `PascalCase` components, one default export per
  component file. CSS classes are semantic kebab-case, block-first
  (`chain-header`, `rep-delete-button`) — no utility classes.
- **API JSON stays `snake_case`** end to end. The frontend reads `daily_score`
  and `rep_type_name` directly; there is no case-converting layer.

## Types

- Python 3.11+, `from __future__ import annotations` in every model and schema.
  SQLAlchemy 2 `Mapped[...]` / `mapped_column(...)` throughout — never the
  legacy `Column()` style. Nullability is expressed as `Mapped[str | None]`.
- No type checker runs in CI. `pytest` covers the backend (`backend/tests/`),
  installed with `pip install -e ".[dev]"`; nothing runs it automatically. Ruff is configured
  (`line-length = 100`, `target-version = "py311"`) but is not wired to
  anything.
- External data becomes a trusted type exactly once, at the Pydantic boundary.
  After that, handlers work with model instances, not dicts.
- Frontend is plain JSX. `@types/react` is installed but no `.ts` file exists —
  do not start migrating to TypeScript as a side effect of another unit.

## FastAPI Conventions

- One `APIRouter` per file in `app/routers/`, with `prefix` and `tags` set at
  construction. Registered explicitly in `main.py`.
- **Mixed nesting is deliberate:** create and list are nested under the parent
  (`POST /goals/{goal_id}/rep-types`), while read, update and delete are flat by
  child id (`PATCH /rep-types/{id}`). Keep this shape.
- Sessions arrive as `session: AsyncSession = Depends(get_session)`. Nothing
  builds its own engine in the request path.
- `response_model` on every route. `status_code=201` on creates,
  `204_NO_CONTENT` on deletes.
- `@app.on_event("startup")` is the current pattern in `main.py`. It is
  deprecated in favour of a lifespan context manager; leave it until a unit
  addresses it, and do not add a second startup hook alongside it.

## API Contract

- Parse, then assert cross-entity constraints, then mutate, then commit, then
  sync the calendar, then commit again. In that order.
- `404` for a missing entity, `409` for a conflicting state (duplicate goal
  title, completing a non-pending rep), `400` for a valid-shaped payload with an
  invalid relationship. `HTTPException(detail=...)` carries a plain human
  sentence, never an exception string.
- Server-owned fields are never accepted from the client: `duration_minutes` is
  copied from the rep type at creation even though the schema declares it, and
  `status` is absent from `RepUpdate` entirely.
- Reads return arrays, not envelopes. `GET /goals` returns `[…]`.

## Errors and Failure

- Routers raise `HTTPException`. Services do not raise — they catch, log, and
  return a degraded value (`None`, `b""`, or an error string in the debrief
  body).
- `google_calendar.py` uses `logging.getLogger(__name__)` with
  `logger.warning("Calendar sync skipped: …")`. `scheduler.py`, `email.py` and
  `debrief.py` use bare `print()`. **`logging` is the chosen convention; the
  `print()` calls are cleanup.**
- A secret must never appear in a log line. The current messages log exception
  text from SDK calls, which is safe today but is the place where a token could
  leak — check before adding a log to an authenticated call path.
- The user sees the fixed string thrown by `api.js` for the endpoint, never a
  backend `detail` and never a stack trace.

## Data Access

- Queries live in `app/services/summary.py` and `app/services/debrief.py`, or
  inline in a router for a single-entity `session.get(...)`. Never in a
  component, never in a template.
- **`session.get(Model, id)` for a primary-key fetch; `select()` for anything
  else.** No raw SQL anywhere in the repo — keep it that way.
- Relationship loading: the codebase currently uses `await session.refresh(obj,
  ["rep_type", "goal"])` inside loops, which is an N+1 and is logged as debt.
  **New code uses `selectinload()` on the `select()`.** Do not copy the
  `refresh`-in-a-loop pattern.
- Counting: use `select(func.count())`. The existing
  `len(result.scalars().all())` pattern loads every row to count it and is debt.
- Transactions: one implicit transaction per session, committed explicitly in
  the route. `expire_on_commit=False` is set, so ORM objects stay readable after
  commit — that is why `return goal` works after `await session.commit()`.
- Bulk status changes use a single `update()` statement, not a Python loop.

## Time

- **`settings.tz` is the only source of "now".** `datetime.now(tz=settings.tz)`
  for timestamps, `.date()` off that for today. `date.today()` and naive
  `datetime.now()` are both defects.
- Weeks are **Monday-start** (`target_date - timedelta(days=target_date.weekday())`).
  `debrief.py` currently disagrees; `summary.py` is correct.
- `scheduled_date` (`Date`) and `scheduled_time` (`Time`) are stored separately
  and combined only when building a calendar event.

## Styling

- Tokens from `frontend/src/styles/dashboard.css` `:root` only. One stylesheet
  for the whole app; add a rule to it rather than creating a second file.
- No inline `style` for color. Inline `style` is acceptable only for a computed
  geometric value (a bar width percentage, an SVG coordinate).
- SVG `stroke`/`fill` must use `var(--…)`. The existing charts hardcode hex —
  that is a divergence, not the standard.

## Async

- Every route handler and every service function is `async def`.
- **A synchronous third-party SDK is always wrapped in
  `await asyncio.to_thread(...)`.** This is the house pattern for Google
  Calendar, Anthropic and `smtplib` alike. Never call a blocking SDK directly,
  and do not introduce an async client for one integration while the others stay
  sync — pick one and change all three in the same unit.

## Anthropic API

- Called through the official `anthropic` SDK, never raw HTTP.
- Current model string is `claude-opus-4-8`. The current default is
  `claude-opus-5`; if the debrief prompt is revised, move the model with it.
- Model strings are exact and carry no date suffix.

## File Organization

- `backend/app/models/` — one file per table, re-exported from `__init__.py` in
  dependency order (Goal, then RepType, then Rep).
- `backend/app/schemas/` — one file per resource. `__init__.py` is empty on
  purpose; import from the module.
- `backend/app/routers/` — one file per resource or view.
- `backend/app/services/` — one file per concern: metrics, debrief, calendar, email.
- `backend/app/db/` — `base.py` (the single `Base`), `session.py` (engine,
  factory, `get_session`).
- `backend/alembic/versions/` — applied migrations.
- `backend/scripts/` — one-time operator scripts, run by hand.
- `frontend/src/components/` — one component per file.
- `frontend/src/api.js` — every fetch.
- `context/` — these files. `context/specs/` — the build plan and unit specs.

## Do Not Touch

- `backend/alembic/versions/*` — both revisions are applied. Schema changes get
  a new revision.
- `backend/.env` — real secrets, gitignored. Never read it into a response,
  never print it, never commit it.
- `frontend/package-lock.json` — regenerated by npm only.
- `backend/daily_tracker.egg-info/` — build output.
- `backend/app/routers/dashboard.py`, `backend/app/templates/`,
  `backend/app/static/` — the unregistered server-rendered dashboard. Dead, and
  its removal is a tracked unit; do not extend it and do not "fix" it.
