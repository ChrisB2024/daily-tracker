# Daily Tracker — Backend

FastAPI + async SQLAlchemy 2 + Postgres. Owns the data model, computes every
metric at read time, and drives the Google Calendar mirror, the weekly debrief
and two scheduled jobs.

Read `../context/` before changing anything — `architecture.md` in particular,
whose **Known Violations** table is the real backlog. `../readme.md` remains the
authority on product behaviour.

## Run it locally

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env          # then set DATABASE_URL
createdb daily_tracker
alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

Port 8000 matches the container and the frontend's dev proxy. API docs at
http://localhost:8000/docs; there is no server-rendered page at `/`.

The frontend runs separately: `cd ../frontend && npm run dev` on port 5173,
proxying to 8000. Set `VITE_API_URL` to point it somewhere else.

## Verify a change

```bash
python scripts/smoke.py                     # against a running local server
python scripts/smoke.py --url https://...   # read-only, safe against production
```

Hits every GET endpoint, checks the response shapes the frontend reads, and
asserts a few invariants. Exits non-zero on failure. There is no unit test suite
and no typecheck in CI, so this plus running the endpoints you touched is the
bar. `--include-debrief` also generates a debrief, which calls Anthropic and
ElevenLabs and costs money.

## Google Calendar

One-way: tracker → calendar, scoped to `calendar.events`, write-only. Reps are
created gray, patched green on completion and red when swept as missed.

The refresh token expires. To mint a new one:

```bash
python scripts/google_oauth.py
```

It prints an authorization URL, waits on `127.0.0.1:8080` for the callback, and
prints `GOOGLE_REFRESH_TOKEN=...`. Put it in `.env` **and** in Railway — they are
separate environments. If Google returns no refresh token the script exits
non-zero rather than writing `None`.

## Scheduled jobs

Both run in-process via APScheduler, pinned to `APP_TIMEZONE`:

| Job | When | What |
| --- | --- | --- |
| `end_of_day_sweep` | 23:59 daily | Pending reps for days that have ended become missed, and their events turn red |
| `weekly_debrief` | Sunday 21:00 | Generates the debrief and emails it with an MP3 attached |

Startup logs each job's resolved next run time. Check it after any timezone
change — the container is UTC, so a missing timezone is invisible locally.

## Layout

| Path | Owns |
| --- | --- |
| `app/models/` | Table shape, enums, relationships |
| `app/schemas/` | The wire contract |
| `app/routers/` | HTTP shape, status codes, cross-entity assertions |
| `app/services/` | Metrics, debrief, and every third-party integration |
| `app/db/` | Engine, session factory, the `get_session` dependency |
| `alembic/versions/` | Applied migrations — never edit one, add a revision |
| `scripts/` | Operator scripts, run by hand |
