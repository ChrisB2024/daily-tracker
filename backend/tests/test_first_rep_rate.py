"""
First rep before noon: per goal, over days a first rep was scheduled, measured
on completed_at rather than scheduled_time.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.models import GoalStatus, RepStatus, RepTypeStatus
from app.services.summary import get_first_rep_rate

TZ = ZoneInfo("America/New_York")
MONDAY = date(2026, 8, 31)
SUNDAY = date(2026, 9, 6)


def at(day, hour):
    return datetime.combine(day, time(hour, 0)).replace(tzinfo=TZ)


async def test_measures_completion_not_scheduling(session, factory):
    """
    The defect this replaced: it filtered on scheduled_time, so a rep booked for
    09:00 and finished at 15:00 counted, and one booked for 14:00 and finished at
    08:00 did not.
    """
    g = await factory.goal()
    rt = await factory.rep_type(g, is_first_rep=True)

    # scheduled early, finished late -> miss
    await factory.rep(rt, on=MONDAY, at=time(9, 0),
                      status=RepStatus.completed, completed_at=at(MONDAY, 15))
    # scheduled late, finished early -> hit
    tue = MONDAY + timedelta(days=1)
    await factory.rep(rt, on=tue, at=time(14, 0),
                      status=RepStatus.completed, completed_at=at(tue, 8))

    [r] = await get_first_rep_rate(session, SUNDAY, TZ)
    assert (r.days_hit, r.days_scheduled) == (1, 2)
    assert r.rate == 0.5


async def test_denominator_is_scheduled_days_not_seven(session, factory):
    g = await factory.goal()
    rt = await factory.rep_type(g, is_first_rep=True)
    await factory.rep(rt, on=MONDAY, status=RepStatus.completed, completed_at=at(MONDAY, 10))

    [r] = await get_first_rep_rate(session, SUNDAY, TZ)
    assert r.rate == 1.0, "one scheduled day, hit — not 1/7"
    assert r.days_scheduled == 1


async def test_noon_is_exclusive(session, factory):
    g = await factory.goal()
    rt = await factory.rep_type(g, is_first_rep=True)
    await factory.rep(rt, on=MONDAY, status=RepStatus.completed, completed_at=at(MONDAY, 12))

    [r] = await get_first_rep_rate(session, SUNDAY, TZ)
    assert r.days_hit == 0, "12:00 exactly is not before noon"


async def test_completed_without_a_timestamp_does_not_raise(session, factory):
    """Legacy rows exist with status=completed and completed_at NULL."""
    g = await factory.goal()
    rt = await factory.rep_type(g, is_first_rep=True)
    await factory.rep(rt, on=MONDAY, status=RepStatus.completed, completed_at=None)

    [r] = await get_first_rep_rate(session, SUNDAY, TZ)
    assert r.days_hit == 0


async def test_nothing_scheduled_is_none_not_zero(session, factory):
    """"None planned" and "planned and missed" are different facts."""
    g = await factory.goal()
    await factory.rep_type(g, is_first_rep=True)

    [r] = await get_first_rep_rate(session, SUNDAY, TZ)
    assert r.rate is None
    assert r.days_scheduled == 0


async def test_archived_rep_types_and_paused_goals_are_excluded(session, factory):
    active = await factory.goal("Active")
    paused = await factory.goal("Paused", status=GoalStatus.paused)
    await factory.rep_type(active, name="Live", is_first_rep=True)
    await factory.rep_type(active, name="Archived", is_first_rep=True,
                           status=RepTypeStatus.archived)
    await factory.rep_type(paused, name="OnPausedGoal", is_first_rep=True)

    rates = await get_first_rep_rate(session, SUNDAY, TZ)
    assert [r.goal_title for r in rates] == ["Active"]


async def test_rate_is_per_goal(session, factory):
    a = await factory.goal("Goal A")
    b = await factory.goal("Goal B")
    rta = await factory.rep_type(a, is_first_rep=True)
    rtb = await factory.rep_type(b, is_first_rep=True)
    await factory.rep(rta, on=MONDAY, status=RepStatus.completed, completed_at=at(MONDAY, 10))
    await factory.rep(rtb, on=MONDAY, status=RepStatus.completed, completed_at=at(MONDAY, 16))

    rates = {r.goal_title: r.rate for r in await get_first_rep_rate(session, SUNDAY, TZ)}
    assert rates == {"Goal A": 1.0, "Goal B": 0.0}
