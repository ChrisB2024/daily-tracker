"""
Debrief payload. No network — generate_debrief_text is never called here.
"""

from datetime import date, timedelta

from app.config import settings
from app.models import RepStatus
from app.services.debrief import get_weekly_summary_data, store_weekly_summary

MONDAY = date(2026, 8, 31)
SUNDAY = date(2026, 9, 6)


async def test_week_is_monday_to_sunday_and_includes_the_day_it_runs(session, factory):
    """
    debrief.py derived its own Sunday-start week, so the Sunday 21:00 job
    reported the previous Sun-Sat and excluded the day it ran.
    """
    g = await factory.goal()
    rt = await factory.rep_type(g)
    await factory.rep(rt, on=SUNDAY, status=RepStatus.completed)

    d = await get_weekly_summary_data(session, SUNDAY, settings.tz)
    assert d["week_start"] == MONDAY.isoformat()
    assert d["week_end"] == SUNDAY.isoformat()
    assert d["completed"] == 1, "the Sunday it runs is in scope"


async def test_most_avoided_ranks_by_expectation_not_raw_count(session, factory):
    """A rarely scheduled rep type must not always win."""
    g = await factory.goal()
    busy = await factory.rep_type(g, name="Busy", weekly_target=10)
    rare = await factory.rep_type(g, name="Rare", weekly_target=1)

    for n in range(3):  # 3 of 10 expected
        await factory.rep(busy, on=MONDAY + timedelta(days=n), status=RepStatus.completed)
    await factory.rep(rare, on=MONDAY, status=RepStatus.completed)  # 1 of 1

    d = await get_weekly_summary_data(session, SUNDAY, settings.tz)
    assert d["most_avoided"]["rep_type_name"] == "Busy"


async def test_rep_types_with_no_cadence_are_not_ranked(session, factory):
    """Nothing stated to fall short of."""
    g = await factory.goal()
    await factory.rep_type(g, name="No cadence", daily_floor=None, weekly_target=None)

    d = await get_weekly_summary_data(session, SUNDAY, settings.tz)
    assert d["most_avoided"] is None


async def test_payload_carries_no_rep_notes(session, factory):
    """Security invariant 4: aggregates and titles leave the system, not content."""
    import json

    g = await factory.goal()
    rt = await factory.rep_type(g)
    await factory.rep(rt, on=MONDAY, status=RepStatus.completed,
                      notes="SECRET-CONTENT-MUST-NOT-LEAK")

    d = await get_weekly_summary_data(session, SUNDAY, settings.tz)
    assert "SECRET-CONTENT-MUST-NOT-LEAK" not in json.dumps(d)


async def test_payload_is_json_serialisable(session, factory):
    """Unit 11 stores this as JSONB; UUID keys would fail there, not here."""
    import json

    g = await factory.goal()
    rt = await factory.rep_type(g)
    await factory.rep(rt, on=MONDAY, status=RepStatus.completed)

    json.dumps(await get_weekly_summary_data(session, SUNDAY, settings.tz))


async def test_storing_a_week_twice_upserts(session, factory):
    from sqlalchemy import func, select

    from app.models import WeeklySummary

    g = await factory.goal()
    rt = await factory.rep_type(g)
    await factory.rep(rt, on=MONDAY, status=RepStatus.completed)

    d = await get_weekly_summary_data(session, SUNDAY, settings.tz)
    await store_weekly_summary(session, d)
    await store_weekly_summary(session, d)

    count = (await session.execute(select(func.count()).select_from(WeeklySummary))).scalar_one()
    assert count == 1


async def test_stored_summary_holds_no_prose(session, factory):
    """
    Decided 2026-09-07: S2 permits an unauthenticated API only while the database
    holds rep metadata. A behavioural narrative is a different class of data.
    """
    import json

    from sqlalchemy import select

    from app.models import WeeklySummary

    g = await factory.goal()
    rt = await factory.rep_type(g)
    await factory.rep(rt, on=MONDAY, status=RepStatus.completed)

    d = await get_weekly_summary_data(session, SUNDAY, settings.tz)
    await store_weekly_summary(session, d)

    row = (await session.execute(select(WeeklySummary))).scalar_one()
    assert not hasattr(row, "text_summary")
    assert "summary" not in json.dumps(row.rep_data)
