"""
Test fixtures.

Every test runs against a throwaway database created and dropped per session.
The real DATABASE_URL is overridden **before app.config is imported**, so there
is no path by which a test can reach the development or production database —
the rep history is the product, and a test suite must not be able to touch it.
"""

import asyncio
import os
import subprocess
import uuid

import pytest

TEST_DB = f"daily_tracker_test_{uuid.uuid4().hex[:8]}"
TEST_URL = f"postgresql+asyncpg://chrisilias@localhost:5432/{TEST_DB}"

# Must happen at import time, before anything reads settings.
os.environ["DATABASE_URL"] = TEST_URL
os.environ["APP_TIMEZONE"] = "America/New_York"
# No third-party calls from tests, ever.
os.environ["GOOGLE_REFRESH_TOKEN"] = ""
os.environ["CLAUDE_API_KEY"] = ""
os.environ["ELEVENLABS_API_KEY"] = ""
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASSWORD"] = ""


def _drop_stale_test_databases():
    """
    A hard-killed run leaks its database. Clean up any earlier ones by name
    prefix — never anything else.
    """
    out = subprocess.run(["psql", "-lqt"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        name = line.split("|")[0].strip()
        if name.startswith("daily_tracker_test_") and name != TEST_DB:
            subprocess.run(["dropdb", "--if-exists", name], check=False)


@pytest.fixture(scope="session", autouse=True)
def _database():
    _drop_stale_test_databases()
    subprocess.run(["createdb", TEST_DB], check=True)
    try:
        subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            env={**os.environ, "DATABASE_URL": TEST_URL},
        )
        yield
    finally:
        asyncio.run(_dispose())
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=False)


async def _dispose():
    from app.db.session import engine

    await engine.dispose()


@pytest.fixture
async def clean_tables():
    """
    Truncate before a test that touches the database, so each starts from a known
    state and order cannot matter. Deliberately not autouse — pure-function tests
    should not open a connection at all.
    """
    from sqlalchemy import text

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        await s.execute(
            text("TRUNCATE reps, rep_types, goals, weekly_summaries RESTART IDENTITY CASCADE")
        )
        await s.commit()
    yield


@pytest.fixture
async def session(clean_tables):
    """A session against the test database, with tables truncated first."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        yield s


@pytest.fixture
async def client(clean_tables):
    """httpx client bound to the app, sharing the test database."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
async def factory(session):
    """Builds a goal, a rep type and reps without going through the API."""
    from datetime import date, time

    from app.models import Goal, Rep, RepStatus, RepType

    class Factory:
        def __init__(self, s):
            self.s = s

        async def goal(self, title="Goal", **kw):
            g = Goal(title=title, **kw)
            self.s.add(g)
            await self.s.commit()
            await self.s.refresh(g)
            return g

        async def rep_type(self, goal, name="Rep type", **kw):
            kw.setdefault("criterion", "one line")
            kw.setdefault("duration_minutes", 30)
            kw.setdefault("daily_floor", 1)
            rt = RepType(goal_id=goal.id, name=name, **kw)
            self.s.add(rt)
            await self.s.commit()
            await self.s.refresh(rt)
            return rt

        async def rep(self, rep_type, on: date, at=time(9, 0), **kw):
            kw.setdefault("status", RepStatus.pending)
            r = Rep(
                rep_type_id=rep_type.id,
                goal_id=rep_type.goal_id,
                scheduled_date=on,
                scheduled_time=at,
                duration_minutes=30,
                **kw,
            )
            self.s.add(r)
            await self.s.commit()
            await self.s.refresh(r)
            return r

    return Factory(session)
