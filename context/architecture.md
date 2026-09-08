# Architecture

Recovered from code on 2026-09-07. Every row in Stack, Ownership, Storage,
Lifecycles and Trust Boundaries is observed fact. Invariants are Chris's
declared rules (from `readme.md`'s Non-Negotiables, plus technical rules the
code consistently follows); each one that the code currently breaks is listed in
**Known Violations** rather than quietly softened.

## Stack

| Layer | Choice | Why this one |
| ----- | ------ | ------------ |
| API framework | FastAPI (async) | Every request fans out to Google / Anthropic / ElevenLabs / SMTP; async keeps one process enough for one user. Auto-generated `/docs` is the only API client Chris needs. |
| ORM | SQLAlchemy 2.x async + asyncpg | Typed `Mapped[]` models; async driver matches the framework. |
| Migrations | Alembic, async `env.py` | `env.py` drives the sync migration API through `run_sync()` and reads the same `DATABASE_URL` as the app, so there is one source of truth for connection config. |
| Database | Postgres | Native UUID, `Date`/`Time` columns, enum types. Data is relational (Goal → RepType → Rep) with no document-shaped payloads. |
| Frontend | React 19 + Vite, no router, no state library | One user, seven views, all state fetched per view. A router would add deep-linking nobody asked for. |
| Styling | One hand-written CSS file with `:root` custom properties | 1524 lines, semantic kebab-case class names. No Tailwind, no CSS modules. |
| Calendar | Google Calendar API v3 (`google-api-python-client`) | The mirror. Scoped to `calendar.events`, used write-only. |
| LLM | `anthropic` SDK, model `claude-opus-4-8` | Generates the weekly debrief prose from aggregated counts. |
| TTS | `elevenlabs` SDK, `eleven_turbo_v2_5`, voice `21m00Tcm4TlvDq8ikWAM` | Audio debrief. |
| Email | `smtplib` + Gmail SMTP (app password) | Stopgap delivery channel for the Sunday debrief. |
| Scheduler | APScheduler `AsyncIOScheduler`, started in FastAPI's `startup` hook | In-process, one job. No external cron, no worker process. |
| Deploy | Docker on Railway; frontend hosted separately via `VITE_API_URL` | `CMD` runs `alembic upgrade head \|\| true` then uvicorn on a fixed port 8000. |

## Ownership Map

| Area | Owns | Must not |
| ---- | ---- | -------- |
| `backend/app/models/` | Table shape, enums, relationships, cascade policy | Import from `routers/`, `services/`, or `schemas/`. Contain query logic or business rules. |
| `backend/app/schemas/` | The wire contract — what the client may send, what it gets back | Contain business logic. Expose a field the client must not set (`status` is deliberately absent from `RepUpdate`). |
| `backend/app/routers/` | HTTP shape, path/param parsing, status codes, cross-entity assertions before insert, calling one service | Compute metrics inline. Talk to a third-party SDK directly — that goes through `services/`. |
| `backend/app/services/` | Metric computation (`summary.py`), debrief pipeline (`debrief.py`), and every third-party integration (`google_calendar.py`, `email.py`) | Import from `routers/`. Raise a third-party exception into a request handler. |
| `backend/app/db/` | The single `Base`, the async engine, the `get_session` per-request dependency | Be bypassed — no module may build its own engine for request-path work. `scheduler.py` currently does, for a job outside the request path. |
| `backend/alembic/versions/` | Applied schema history | Be edited after being applied. New change means a new revision. |
| `frontend/src/api.js` | Every `fetch` in the app, one exported function per endpoint | Be bypassed — no component calls `fetch` directly. |
| `frontend/src/components/` | Rendering and local view state | Contain a URL or a fetch. Compute a metric the API already returns. |
| `frontend/src/styles/dashboard.css` | Every color, spacing and layout decision | Be bypassed by inline styles — though the SVG charts currently do exactly that. |

**Dead code, kept but unowned:** `backend/app/routers/dashboard.py`,
`backend/app/templates/dashboard.html` and `backend/app/static/style.css` are
the Slice-1/3 server-rendered dashboard. `dashboard.py` is not registered in
`main.py`, so the Jinja dashboard is unreachable. `frontend/src/components/ChainsList.jsx`
and `ChainsVisualization.jsx` are imported by nothing.

## Data Flow

**The write path.** Browser → `api.js` → FastAPI router → Pydantic parse →
cross-entity assertion (`rep_type.goal_id == payload.goal_id`) → `session.add` →
commit → `GoogleCalendarClient` → Google Calendar → returned `event.id` written
back onto the rep → second commit. The tracker is the source of truth at every
step; the calendar never writes back.

**The read path.** Browser → `api.js` → router → `services/summary.py` → many
small `select()` queries over `reps` → aggregated in Python → Pydantic response
model → JSON. Nothing is cached, nothing is precomputed, no metric is stored.

**The debrief path.** Sunday job (or `GET /debrief`) → aggregate the week from
`reps` → prompt text containing week counts **and goal titles** → Anthropic →
prose → ElevenLabs → MP3 bytes → Gmail SMTP → Chris's inbox. Nothing on this
path is persisted.

**Who can read what.** Everything. The API has no authentication, so any holder
of the URL can read and write every goal, rep type and rep. This is an accepted
risk (see Security invariant S2), and it is the reason the storage rule below is
binding rather than advisory.

## Storage Model

- **Postgres** — `goals`, `rep_types`, `reps`. Three tables, all UUID
  primary keys, all `created_at` defaulted server-side with `now()`.
- **Environment variables** — every secret: `DATABASE_URL`,
  `GOOGLE_CLIENT_ID` / `_SECRET` / `_REFRESH_TOKEN`, `CLAUDE_API_KEY`,
  `ELEVENLABS_API_KEY`, `SMTP_USER` / `_PASSWORD`. Loaded once into a
  module-level `Settings` singleton in `config.py`. `backend/.env` is gitignored;
  production values live in Railway's environment.
- **Google Calendar** — the display copy of rep state. Event carries
  `extendedProperties.private.rep_id`, so an event can be traced back to a rep.
  Never read back.
- **Nowhere** — debriefs (text and audio), chains, scores, PRs, rates. All
  ephemeral or recomputed.

**Never stored in Postgres:** secrets or third-party tokens of any kind; audio
blobs; generated debrief text; any computed metric. The Google refresh token
lives in the environment specifically so a database read cannot yield calendar
write access.

## Entity Lifecycles

| Entity | Created by | Modified by | Ends how | What happens to related data |
| ------ | ---------- | ----------- | -------- | ---------------------------- |
| `Goal` | `POST /goals` (409 on duplicate title, checked in Python, no DB constraint) | `PATCH /goals/{id}` — any field including `status`, no transition guard | `DELETE` → `status = archived` (default) · `DELETE ?hard=true` → row purged | Soft: rep types and reps untouched, and still counted by every metric. **Hard: all reps and rep types deleted first, destroying the evidence trail.** Their calendar events are now deleted first too (fixed 2026-09-07); previously they were stranded in Google Calendar. |
| `RepType` | `POST /goals/{goal_id}/rep-types` — 404 if goal missing | `PATCH /rep-types/{id}` | `DELETE` → `status = archived` only. No hard delete. | Reps preserved by design (`cascade="save-update, merge"`, no delete cascade). Archiving now actually retires the type: it drops out of `get_chains` (Unit 02) and out of `GET /goals/{id}/rep-types` unless `include_archived=true` (fixed 2026-09-07). `get_rep_type_analytics` still does not filter on status. |
| `Rep` | `POST /reps` or `POST /reps/bulk` — both assert the rep type belongs to the goal, and copy `duration_minutes` from the rep type | `PATCH /reps/{id}` (date, time, duration, notes — **does not re-sync the calendar event**) · `POST /reps/{id}/complete` · `POST /reps/mark-missed` | `DELETE /reps/{id}` — hard delete, plus calendar event deletion | Calendar event deleted with the rep. A `PATCH` that moves the rep leaves the event at the old time forever. |
| Calendar event | Created alongside a rep; `rep.calendar_event_id` stores the id | `patch_color` on complete (10) and miss (11) | Deleted with the rep | Orphaned whenever `create_event` returns `None` (its exception handler swallows the failure), or whenever the rep is rescheduled. |
| `WeeklySummary` | — | — | — | **Not implemented.** Specified in `readme.md`; no model, no table. Debriefs cannot be retrieved after generation. |

## State Machines

**Rep:** `pending --POST /{id}/complete--> completed` · `pending --POST /reps/mark-missed--> missed`

Both are terminal. Enforced by three things together: `RepUpdate` omits
`status`, `complete_rep` returns 409 unless the rep is `pending`, and the
`mark_missed` bulk `UPDATE` filters `status == pending`.

- Unreachable by design: `completed → missed`, `missed → completed`, anything
  `→ pending`. There is deliberately no un-complete and no un-miss.

**Goal:** `active ↔ paused ↔ completed → archived`, all via `PATCH .status`,
plus `archived` via `DELETE`. No transition is guarded server-side; the
confirmation lives in the UI only (`confirm()` in `GoalsManagement.jsx`).

**RepType:** `active → archived` via `DELETE`; `archived → active` is reachable
via `PATCH`. Intentional — a paused domain can be resumed.

## Trust Boundaries

| Crossing | From → to | Enforced how |
| -------- | --------- | ------------ |
| Browser → API | untrusted → trusted | Pydantic parses every body and every path/query param. `criterion` carries `min_length=1`. Create routes assert the rep type belongs to the stated goal before inserting. **No authentication and no authorization** — accepted (S2). CORS is `allow_origins=["*"]` with `allow_credentials=True`. |
| API → Postgres | trusted → trusted | SQLAlchemy Core/ORM only. No raw SQL, no string-built queries anywhere in the repo. |
| API → Google Calendar | trusted → semi-trusted | OAuth refresh-token grant, scoped to `calendar.events` only. Runs in `asyncio.to_thread`. Every operation wraps its own try/except, logs a warning, and returns `None` rather than raising. **Rep type names, goal titles and rep notes leave the system here.** |
| API → Anthropic | trusted → semi-trusted | API key from env. Week counts **and goal titles** are sent in the prompt. Rep notes are not. All exceptions caught and converted to an error string in the summary body. |
| API → ElevenLabs | trusted → semi-trusted | API key from env. The debrief text, which contains goal titles, is sent. Failure returns empty bytes. |
| API → Gmail SMTP | trusted → semi-trusted | STARTTLS on port 587, app password from env. Recipient is always `settings.smtp_user` — the sender mails himself. |
| `scripts/google_oauth.py` → 127.0.0.1:8080 | one-time local loopback | `InstalledAppFlow` with `open_browser=False`; refresh token printed to stdout for manual paste into `.env`. Exits non-zero if Google returns no refresh token. |

## Invariants

Rules the system must never break. The Product set is Chris's own
Non-Negotiables from `readme.md`, restated as checkable rules.

### Technical

1. **Rep status changes only through `/complete` and `/mark-missed`.** No
   endpoint accepts `status` as an input field.
2. **Chains, scores, PRs and rates are computed at read time from the `reps`
   table.** No metric is ever written onto a `Rep`, `RepType` or `Goal` row.
3. **Every `Rep` carries both `rep_type_id` and `goal_id`, NOT NULL, and the
   rep type must belong to the stated goal.** Enforced at the database and
   re-asserted in both create routes.
4. **All date and time-of-day arithmetic uses `settings.tz`.** Never
   `date.today()`, never naive `datetime.now()`, never container-local time.
5. **A third-party call never raises into a request handler.** Every integration
   in `services/` catches its own exceptions, logs, and degrades to `None` or
   empty output.
6. **Third-party SDKs are synchronous and are always called through
   `asyncio.to_thread`.** The event loop is never blocked.

### Product

1. **Every rep tags to a rep type; every rep type tags to a goal.** No orphans,
   no untyped reps.
2. **Every rep type has a non-empty one-line criterion.** Required at creation.
   If it cannot be written, it is not a rep.
3. **Missed reps stay visible as missed.** Never deleted, never hidden, never
   reclassified. Erasing a missed rep erases the evidence the system exists to
   collect.
4. **Chains are independent per rep type, and are shown to the user.** Breaking
   one must never break another, and a chain the user is holding must be legible
   on the dashboard.
5. **The calendar is a mirror, never a source.** Sync is one-way. Nothing read
   from Google Calendar may ever change tracker state.
6. **The Sunday debrief reports findings, not encouragement.** Built from rep
   data only, never self-report. No motivational language, no praise, no emoji —
   chains, numbers and patterns.
7. **Nothing irreversible happens without confirmation**, and every view that
   renders data renders a real empty, loading and error state.

### Security

1. **Secrets live only in environment variables.** Never in code, never in a
   log line, never in a response body, never in the client bundle. `backend/.env`
   stays gitignored.
2. **The API is deliberately unauthenticated and single-user — an accepted
   risk, not an oversight.** Chris confirmed this on 2026-09-07: the URL is the
   only secret. The binding consequence: **the database may hold only rep
   metadata.** No credentials, no third-party tokens, no sensitive personal
   content in `notes`. Do not add authentication without being asked, and do not
   store anything whose disclosure would matter.
3. **Google OAuth stays scoped to `calendar.events` and write-only.** The
   tracker never reads calendar state. The refresh token lives in the
   environment, never in Postgres, so a database compromise cannot yield
   calendar access.
4. **Debrief payloads carry aggregates, not raw content.** Counts and goal
   titles may leave the system; rep notes may not.

## Least Privilege

- **Database role** — the app connects as the `DATABASE_URL` user, which also
  runs Alembic at container start, so it necessarily holds DDL rights. Accepted
  for a single-user deploy; it is the one privilege here wider than the app's
  request-path needs.
- **Google OAuth** — `https://www.googleapis.com/auth/calendar.events`. No
  `calendar.readonly`, no `calendar` full scope, no other Google API.
- **Gmail** — an app password, not the account password. Used to send to one
  recipient: the sender.
- **Anthropic / ElevenLabs** — one key each, no org-admin key.
- **Frontend** — receives no secret. `VITE_API_URL` is the only build-time
  variable and it is a public URL.

## Known Violations

Where the code breaks its own rules today. Recorded so no session "discovers"
and silently fixes them, and so none is copied as precedent. Roughly ordered by
what it costs the product.

| Invariant | Violated at | Bug, or soften the rule? |
| --------- | ----------- | ------------------------ |
| Product 4 — weekly-only chains | `backend/app/services/summary.py` — `get_chains` | **Open, carved out of Unit 02.** `readme.md` says a rep type with only a `weekly_target` chains per *week*, and leaves the edge cases TBD. No such rep type exists today (every one has `daily_floor = 1`), so they fall through to the daily walk. Decide the weekly rule before creating one. |
| Product 3 — evidence survives | `backend/app/routers/goals.py:98-104` (`?hard=true`) | **Soften, with the reason recorded.** A deliberate escape hatch for goals created by mistake. It is the one path that destroys reps, it is confirmed twice in the UI, and it should stay the only one. |
| Product 4 — archived rep types | `get_chains` and `get_rep_type_analytics` in `summary.py` both `select(RepType)` with no status filter | **Bug.** Archived rep types keep appearing in chains and analytics, so a domain Chris paused still occupies the dashboard. |
| Security 4 / product honesty | `get_30day_rhythm` in `summary.py:277`, surfaced as `rhythm_30day` | **Bug (naming).** Returns the current calendar month, not 30 days. The name and the API field both misdescribe the data. |
| Technical 5 — calendar failures degrade | `create_event` returns `None` on failure (`google_calendar.py:110`), and callers assign it to `rep.calendar_event_id` without checking | **Bug, at a low rate.** The invariant holds — nothing raises — but a rep that fails to sync is left permanently unsynced with no record and no retry. Measured in production 2026-09-07: 21 of 320 reps (~7%) have no `calendar_event_id`, concentrated in July. Sync is working overall (September: 35/35), so this is occasional silent loss, not an outage. The failure log does not name the event id (`google_calendar.py:84,108,129`), so there is no way to tell which reps failed. Unit 10 addresses it. |
| Product 5 — calendar is a mirror | `update_rep` in `reps.py:126-141` | **Bug.** Changing `scheduled_date`/`scheduled_time` never patches the event, so the mirror silently stops reflecting the tracker. |
| Efficiency (no invariant, but load-bearing) | 13 `session.refresh(...)` calls inside loops; zero `selectinload`/`joinedload` in the repo; `get_summary` runs a chain query *plus* a 60-day history query per rep type; counts use `len(result.scalars().all())` instead of `select(func.count())` | **Bug.** `backend/README.md` itself says to use `selectinload` "to avoid lazy-load explosions". `/summary` is O(rep types × queries) on every dashboard load. |
| Efficiency — OAuth | `GoogleCalendarClient._build_service` refreshes credentials on every single operation, and `create_reps_bulk` constructs a fresh client per rep | **Bug.** Bulk-scheduling 14 reps performs 14 serial token refreshes and 14 service builds. |
| Security 1 — CORS | `backend/app/main.py:11-16` | **Soften and record.** `allow_origins=["*"]` with `allow_credentials=True` is a combination browsers reject outright, so the credentials flag does nothing. Given S2 there is nothing to protect, but the config is misleading and should say what it means. |
