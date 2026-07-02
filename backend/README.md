# Daily Tracker — Backend

## Setup

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# Edit .env: set DATABASE_URL to your local Postgres

# Create the database (once)
createdb daily_tracker

# After you implement models, generate + apply the first migration:
alembic revision --autogenerate -m "initial schema"
alembic upgrade head

# Run the server
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 for the dashboard, http://localhost:8000/docs for the auto-generated API docs.

## Slice 1 TODOs (in order)

Domain model is **Goal → RepType → Rep**. Reps are scheduled instances of RepTypes; RepTypes live under Goals.

1. `app/models/rep.py` — fill in the `rep_type_id` column (NOT NULL FK), the `notes` column, and the `rep_type` relationship.
2. `app/models/rep_type.py` — fill in every TODO column + the `goal` and `reps` relationships.
3. `app/schemas/rep_type.py` — fill in `RepTypeCreate`, `RepTypeUpdate`, `RepTypeRead`.
4. `app/routers/goals.py` — already implemented, just confirm tests still pass.
5. `app/routers/rep_types.py` — implement each endpoint. The `criterion` non-empty rule lives here.
6. `app/routers/reps.py` — implement each endpoint. Pay attention to `complete_rep` and `mark_missed`.
7. `app/routers/dashboard.py` — implement `home()`. Remember `selectinload(Rep.rep_type)` to avoid lazy-load explosions.
8. `app/main.py` — uncomment the router imports + `include_router` calls one by one as each is implemented.
9. Run `alembic revision --autogenerate -m "initial schema"`, eyeball the generated SQL, then `alembic upgrade head`.
10. `uvicorn app.main:app --reload` and check the dashboard renders.

Then ask me to review.
