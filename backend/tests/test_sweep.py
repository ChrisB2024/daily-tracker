"""
The end-of-day sweep. `through` is the last day that has ENDED.
"""

from datetime import date, timedelta

from app.models import RepStatus
from app.services.sweep import sweep_missed

TODAY = date(2026, 9, 7)


async def _statuses(session):
    from sqlalchemy import select

    from app.models import Rep

    rows = (
        await session.execute(select(Rep.scheduled_date, Rep.status).order_by(Rep.scheduled_date))
    ).all()
    return {(d - TODAY).days: s for d, s in rows}


async def test_manual_sweep_leaves_today_alone(session, factory):
    """
    The bug this fixed: pressing the dashboard button at 09:00 marked today's
    still-pending reps as missed.
    """
    g = await factory.goal()
    rt = await factory.rep_type(g)
    await factory.rep(rt, on=TODAY - timedelta(days=3))
    await factory.rep(rt, on=TODAY - timedelta(days=1))
    await factory.rep(rt, on=TODAY)

    swept = await sweep_missed(session, through=TODAY - timedelta(days=1))
    assert swept == 2

    st = await _statuses(session)
    assert st[-3] == RepStatus.missed
    assert st[-1] == RepStatus.missed
    assert st[0] == RepStatus.pending, "today has not ended"


async def test_cron_sweep_closes_out_today(session, factory):
    g = await factory.goal()
    rt = await factory.rep_type(g)
    await factory.rep(rt, on=TODAY)

    assert await sweep_missed(session, through=TODAY) == 1
    assert (await _statuses(session))[0] == RepStatus.missed


async def test_sweep_is_self_healing_after_a_missed_run(session, factory):
    """
    APScheduler does not backfill. `<= through` means a skipped 23:59 run is
    repaired by the next one rather than stranding reps as pending forever.
    """
    g = await factory.goal()
    rt = await factory.rep_type(g)
    for n in (5, 4, 3, 2, 1, 0):
        await factory.rep(rt, on=TODAY - timedelta(days=n))

    assert await sweep_missed(session, through=TODAY) == 6


async def test_sweep_never_touches_completed_or_future_reps(session, factory):
    g = await factory.goal()
    rt = await factory.rep_type(g)
    await factory.rep(rt, on=TODAY - timedelta(days=1), status=RepStatus.completed)
    await factory.rep(rt, on=TODAY + timedelta(days=1))

    assert await sweep_missed(session, through=TODAY) == 0
    st = await _statuses(session)
    assert st[-1] == RepStatus.completed
    assert st[1] == RepStatus.pending


async def test_sweep_is_idempotent(session, factory):
    g = await factory.goal()
    rt = await factory.rep_type(g)
    await factory.rep(rt, on=TODAY - timedelta(days=1))

    assert await sweep_missed(session, through=TODAY) == 1
    assert await sweep_missed(session, through=TODAY) == 0
