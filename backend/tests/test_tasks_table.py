"""
The `tasks` table (Unit 14). No endpoint exists yet, so these check what the
database itself guarantees — the rules later units lean on.
"""

from datetime import date, time
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Task, TaskStatus


def _task(goal_id, event_id="evt-1", **kw):
    kw.setdefault("title", "ship onboarding")
    kw.setdefault("scheduled_date", date(2026, 9, 24))
    kw.setdefault("start_time", time(9, 0))
    kw.setdefault("end_time", time(10, 30))
    kw.setdefault("duration_minutes", 90)
    return Task(goal_id=goal_id, calendar_event_id=event_id, **kw)


async def test_new_task_defaults_to_pending(session, factory):
    g = await factory.goal()
    t = _task(g.id)
    session.add(t)
    await session.commit()
    await session.refresh(t)

    assert t.status == TaskStatus.pending
    assert t.is_all_day is False
    assert t.completed_at is None
    assert t.cancel_reason is None
    assert t.created_at is not None and t.updated_at is not None


async def test_one_event_can_never_become_two_tasks(session, factory):
    """The 15-minute sync upserts on this constraint; it must hold in the database."""
    g = await factory.goal()
    session.add(_task(g.id, event_id="same-event"))
    await session.commit()

    session.add(_task(g.id, event_id="same-event", title="duplicate"))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_task_must_belong_to_a_real_goal(session):
    session.add(_task(uuid4()))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_all_day_task_has_no_times_and_keeps_its_calendar_length(session, factory):
    g = await factory.goal()
    t = _task(
        g.id,
        start_time=None,
        end_time=None,
        is_all_day=True,
        duration_minutes=1440,
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)

    assert t.is_all_day is True
    assert t.start_time is None and t.end_time is None
    assert t.duration_minutes == 1440
