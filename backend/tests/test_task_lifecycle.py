"""
Task check-off, the midnight sweep, and removal reasons (Unit 16).

Google is replaced by RecordingCalendar, which remembers every colour patch, so
"turns green" and "turns red" are asserted without a network.
"""

from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import Task, TaskStatus
from app.services.task_sweep import sweep_missed_tasks


def today():
    return datetime.now(tz=settings.tz).date()


class RecordingCalendar:
    patches: list[tuple[str, int]] = []

    def __init__(self, *args):
        pass

    async def patch_color(self, event_id, color_id):
        RecordingCalendar.patches.append((event_id, color_id))


@pytest.fixture
def calendar(monkeypatch):
    """Turn Google 'on' and route every client through RecordingCalendar."""
    import app.routers.tasks
    import app.services.task_sweep

    RecordingCalendar.patches = []
    monkeypatch.setattr(settings, "google_client_id", "x")
    monkeypatch.setattr(settings, "google_client_secret", "x")
    monkeypatch.setattr(settings, "google_refresh_token", "x")
    monkeypatch.setattr(app.routers.tasks, "GoogleCalendarClient", RecordingCalendar)
    monkeypatch.setattr(app.services.task_sweep, "GoogleCalendarClient", RecordingCalendar)
    return RecordingCalendar


@pytest.fixture
def make_task(session, factory):
    async def make(event_id, on, status=TaskStatus.pending, **kw):
        goal = await factory.goal(f"Goal {event_id}")
        t = Task(
            goal_id=goal.id,
            calendar_event_id=event_id,
            title="x",
            scheduled_date=on,
            start_time=time(9, 0),
            end_time=time(10, 0),
            duration_minutes=60,
            status=status,
            **kw,
        )
        session.add(t)
        await session.commit()
        return t.id

    return make


async def _status(session, task_id):
    session.expire_all()
    return (await session.execute(select(Task.status).where(Task.id == task_id))).scalar_one()


# --- check off ------------------------------------------------------------------


async def test_checking_off_completes_and_turns_the_event_green(client, calendar, make_task):
    tid = await make_task("e1", today())
    r = await client.post(f"/tasks/{tid}/complete")
    assert r.status_code == 200
    assert r.json()["status"] == "completed" and r.json()["completed_at"] is not None
    assert calendar.patches == [("e1", 10)]


async def test_completing_twice_is_409(client, make_task):
    tid = await make_task("e1", today())
    assert (await client.post(f"/tasks/{tid}/complete")).status_code == 200
    assert (await client.post(f"/tasks/{tid}/complete")).status_code == 409


async def test_a_past_day_cannot_be_checked_off(client, session, make_task):
    """Checking off closes at midnight, even if the sweep has not run yet."""
    tid = await make_task("e1", today() - timedelta(days=1))
    assert (await client.post(f"/tasks/{tid}/complete")).status_code == 409
    assert await _status(session, tid) == TaskStatus.pending


async def test_missed_and_cancelled_tasks_cannot_be_completed(client, make_task):
    missed = await make_task("e1", today(), status=TaskStatus.missed)
    cancelled = await make_task("e2", today(), status=TaskStatus.cancelled)
    assert (await client.post(f"/tasks/{missed}/complete")).status_code == 409
    assert (await client.post(f"/tasks/{cancelled}/complete")).status_code == 409


# --- midnight sweep ---------------------------------------------------------------


async def test_sweep_marks_ended_days_missed_and_red(session, calendar, make_task):
    yesterday = today() - timedelta(days=1)
    stale = await make_task("old", yesterday - timedelta(days=2))  # a skipped midnight
    late = await make_task("y", yesterday)
    done = await make_task("d", yesterday, status=TaskStatus.completed)
    gone = await make_task("c", yesterday, status=TaskStatus.cancelled)
    live = await make_task("t", today())

    assert await sweep_missed_tasks(session, through=yesterday) == 2

    assert await _status(session, stale) == TaskStatus.missed
    assert await _status(session, late) == TaskStatus.missed
    assert await _status(session, done) == TaskStatus.completed
    assert await _status(session, gone) == TaskStatus.cancelled
    assert await _status(session, live) == TaskStatus.pending, "today has not ended"
    assert sorted(calendar.patches) == [("old", 11), ("y", 11)]


async def test_a_task_checked_before_midnight_survives_the_sweep(client, session, make_task):
    tid = await make_task("e1", today())
    assert (await client.post(f"/tasks/{tid}/complete")).status_code == 200
    # The sweep for the day that just ended.
    await sweep_missed_tasks(session, through=today())
    assert await _status(session, tid) == TaskStatus.completed


# --- removal reasons ----------------------------------------------------------------


async def test_a_removed_task_takes_one_reason(client, make_task):
    tid = await make_task("e1", today(), status=TaskStatus.cancelled)
    r = await client.post(f"/tasks/{tid}/cancel-reason", json={"reason": "  moved to Friday  "})
    assert r.status_code == 200 and r.json()["cancel_reason"] == "moved to Friday"

    again = await client.post(f"/tasks/{tid}/cancel-reason", json={"reason": "changed my mind"})
    assert again.status_code == 409


async def test_reason_is_dropped_after_its_day(client, make_task):
    tid = await make_task("e1", today() - timedelta(days=1), status=TaskStatus.cancelled)
    r = await client.post(f"/tasks/{tid}/cancel-reason", json={"reason": "too late"})
    assert r.status_code == 409


async def test_only_removed_tasks_take_a_reason(client, make_task):
    tid = await make_task("e1", today())
    r = await client.post(f"/tasks/{tid}/cancel-reason", json={"reason": "x"})
    assert r.status_code == 409


async def test_blank_or_long_reason_is_rejected(client, make_task):
    tid = await make_task("e1", today(), status=TaskStatus.cancelled)
    assert (await client.post(f"/tasks/{tid}/cancel-reason", json={"reason": "   "})).status_code == 422
    assert (await client.post(f"/tasks/{tid}/cancel-reason", json={"reason": "x" * 201})).status_code == 422


async def test_unknown_task_is_404(client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await client.post(f"/tasks/{missing}/complete")).status_code == 404


# --- graph (Unit 18) ------------------------------------------------------------------


async def test_day_graph_links_tasks_to_goals_and_sizes_goals_by_completed_time(
    client, session, factory
):
    a = (await factory.goal("Angle")).id
    h = (await factory.goal("Hitwin")).id
    day = today()

    def task(goal_id, event_id, minutes, status):
        return Task(
            goal_id=goal_id, calendar_event_id=event_id, title=event_id,
            scheduled_date=day, duration_minutes=minutes, status=status,
        )

    session.add_all([
        task(h, "h1", 90, TaskStatus.completed),
        task(h, "h2", 30, TaskStatus.missed),
        task(a, "a1", 45, TaskStatus.completed),
        task(a, "a2", 60, TaskStatus.cancelled),  # deleted event: not drawn
    ])
    await session.commit()

    r = await client.get("/tasks/graph", params={"date": day.isoformat()})
    assert r.status_code == 200
    body = r.json()
    goals = [n for n in body["nodes"] if n["kind"] == "goal"]
    tasks = [n for n in body["nodes"] if n["kind"] == "task"]

    assert [g["label"] for g in goals] == ["Hitwin", "Angle"], "most time first"
    assert goals[0]["minutes_completed"] == 90 and goals[0]["minutes_planned"] == 120
    assert goals[0]["task_count"] == 2 and goals[0]["completed_count"] == 1
    assert sorted(t["label"] for t in tasks) == ["a1", "h1", "h2"], "cancelled left out"
    assert {
        "source": f"task:{tasks[0]['id'][5:]}",
        "target": f"goal:{tasks[0]['goal_id']}",
        "kind": "task",
        "weight": None,
    } in body["links"]
    assert len(body["links"]) == 3


async def test_empty_day_graph(client):
    r = await client.get("/tasks/graph", params={"date": "2020-01-01"})
    assert r.status_code == 200 and r.json()["nodes"] == [] and r.json()["links"] == []


# --- week graph (Unit 19) ---------------------------------------------------------------


async def test_week_graph_covers_monday_to_sunday_and_ranks_goals(client, session, factory):
    from datetime import date as _date

    a = (await factory.goal("Angle")).id
    h = (await factory.goal("Hitwin")).id
    monday = _date(2026, 9, 21)

    def task(goal_id, event_id, on, minutes, status=TaskStatus.completed):
        return Task(goal_id=goal_id, calendar_event_id=event_id, title=event_id,
                    scheduled_date=on, duration_minutes=minutes, status=status)

    session.add_all([
        task(a, "a-mon", monday, 60),
        task(a, "a-sun", monday + timedelta(days=6), 180),
        task(h, "h-wed", monday + timedelta(days=2), 120),
        task(h, "h-prev-sun", monday - timedelta(days=1), 600),  # last week
        task(h, "h-next-mon", monday + timedelta(days=7), 600),  # next week
    ])
    await session.commit()

    # Any day of the week snaps to its Monday.
    r = await client.get("/tasks/graph", params={"week_start": "2026-09-24"})
    assert r.status_code == 200
    body = r.json()
    assert (body["start_date"], body["end_date"]) == ("2026-09-21", "2026-09-27")
    goals = [n for n in body["nodes"] if n["kind"] == "goal"]
    assert [(g["label"], g["minutes_completed"]) for g in goals] == [("Angle", 240), ("Hitwin", 120)]
    # Colour follows creation order (Angle first), not this week's ranking.
    assert [g["color_slot"] for g in goals] == [1, 2]

    # ...so the same goal keeps its colour in a day where the ranking flips.
    day = await client.get("/tasks/graph", params={"date": "2026-09-23"})
    only = [n for n in day.json()["nodes"] if n["kind"] == "goal"]
    assert [(g["label"], g["color_slot"]) for g in only] == [("Hitwin", 2)]
    assert len(body["links"]) == 3


async def test_graph_rejects_day_and_week_together(client):
    r = await client.get("/tasks/graph", params={"date": "2026-09-24", "week_start": "2026-09-21"})
    assert r.status_code == 400


# --- shared-day goal links (Unit 21) ----------------------------------------------------


async def test_week_links_goals_worked_on_the_same_day(client, session, factory):
    from datetime import date as _date

    a = (await factory.goal("Angle")).id
    h = (await factory.goal("Hitwin")).id
    p = (await factory.goal("Physical")).id
    mon = _date(2026, 9, 21)

    def task(goal_id, event_id, on, status=TaskStatus.completed):
        return Task(goal_id=goal_id, calendar_event_id=event_id, title=event_id,
                    scheduled_date=on, duration_minutes=30, status=status)

    tue, wed = mon + timedelta(days=1), mon + timedelta(days=2)
    session.add_all([
        task(a, "a1", mon), task(h, "h1", mon),            # A–H on Monday
        task(a, "a2", tue), task(h, "h2", tue),            # A–H on Tuesday
        task(p, "p1", tue, TaskStatus.missed),             # missed: not "worked"
        task(p, "p2", wed), task(h, "h3", wed, TaskStatus.pending),  # pending: not "worked"
    ])
    await session.commit()

    body = (await client.get("/tasks/graph", params={"week_start": "2026-09-21"})).json()
    shared = [l for l in body["links"] if l["kind"] == "shared_day"]
    assert len(shared) == 1
    assert {shared[0]["source"], shared[0]["target"]} == {f"goal:{a}", f"goal:{h}"}
    assert shared[0]["weight"] == 2
    assert all(l["kind"] == "task" for l in body["links"] if l not in shared)

    day = (await client.get("/tasks/graph", params={"date": "2026-09-21"})).json()
    assert all(l["kind"] == "task" for l in day["links"]), "no goal links in a day graph"
