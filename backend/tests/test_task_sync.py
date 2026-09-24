"""
Calendar → tasks sync (Unit 15).

Google is replaced by FakeCalendar: a dict of events that the test edits between
syncs, exactly as Chris would edit his calendar. No network, ever.
"""

from datetime import date, time
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import GoalStatus, Task, TaskStatus
from app.services.task_sync import parse_event, sync_tasks

TZ = ZoneInfo("America/New_York")
DAY = date(2026, 9, 24)


def timed(event_id, summary, start="2026-09-24T09:00:00-04:00", end="2026-09-24T10:30:00-04:00", **kw):
    return {"id": event_id, "summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}, **kw}


def all_day(event_id, summary, start="2026-09-24", end="2026-09-25"):
    return {"id": event_id, "summary": summary, "start": {"date": start}, "end": {"date": end}}


class FakeCalendar:
    """Stands in for GoogleCalendarClient: list_events and get_event only."""

    def __init__(self, *events):
        self.events = {e["id"]: e for e in events}
        self.reachable = True

    async def list_events(self, time_min, time_max):
        if not self.reachable:
            return None
        out = []
        for e in self.events.values():
            p = parse_event(e, TZ)
            if p is not None and not (time_min.date() <= p.scheduled_date < time_max.date()):
                continue
            out.append(e)
        return out

    async def get_event(self, event_id):
        if not self.reachable:
            return None
        return self.events.get(event_id, {"id": event_id, "status": "cancelled"})


async def _sync(session, cal, start=DAY, end=DAY):
    return await sync_tasks(session, cal, start, end, TZ)


async def _tasks(session):
    session.expire_all()
    return {t.calendar_event_id: t for t in (await session.execute(select(Task))).scalars()}


# --- parse_event: pure, no database -------------------------------------------


def test_parse_timed_event():
    p = parse_event(timed("e1", "[Hitwin] ship onboarding"), TZ)
    assert (p.goal_tag, p.title) == ("Hitwin", "ship onboarding")
    assert p.scheduled_date == DAY
    assert (p.start_time, p.end_time) == (time(9, 0), time(10, 30))
    assert p.duration_minutes == 90 and p.is_all_day is False


def test_parse_converts_to_local_time():
    # 02:00 UTC on the 25th is 22:00 on the 24th in New York.
    p = parse_event(timed("e1", "[A] x", "2026-09-25T02:00:00Z", "2026-09-25T03:00:00Z"), TZ)
    assert p.scheduled_date == DAY and p.start_time == time(22, 0)


def test_parse_all_day_keeps_calendar_length():
    assert parse_event(all_day("e1", "[A] x"), TZ).duration_minutes == 1440
    two_days = parse_event(all_day("e2", "[A] x", "2026-09-24", "2026-09-26"), TZ)
    assert two_days.duration_minutes == 2880 and two_days.start_time is None


def test_parse_ignores_untagged_and_rep_events():
    assert parse_event(timed("e1", "Dentist"), TZ) is None
    assert parse_event(timed("e2", "no [prefix] here"), TZ) is None
    rep_event = timed("e3", "[Build project] Angle", extendedProperties={"private": {"rep_id": "x"}})
    assert parse_event(rep_event, TZ) is None


# --- sync_tasks ----------------------------------------------------------------


async def test_tagged_event_becomes_pending_task_and_resync_is_idempotent(session, factory):
    goal_id = (await factory.goal("Hitwin")).id
    cal = FakeCalendar(timed("e1", "[hitwin] ship onboarding"))  # case-insensitive

    r = await _sync(session, cal)
    assert r.created == 1
    t = (await _tasks(session))["e1"]
    assert t.goal_id == goal_id and t.status == TaskStatus.pending and t.title == "ship onboarding"

    r = await _sync(session, cal)
    assert (r.created, r.updated, r.unchanged) == (0, 0, 1)
    assert len(await _tasks(session)) == 1


async def test_untagged_unmatched_and_rep_events_are_counted_not_imported(session, factory):
    await factory.goal("Hitwin")
    cal = FakeCalendar(
        timed("e1", "Team meeting"),
        timed("e2", "[Hitwn] typo"),
        timed("e3", "[Build project] Angle", extendedProperties={"private": {"rep_id": "r"}}),
    )
    r = await _sync(session, cal)
    assert (r.created, r.untagged, r.rep_events_skipped) == (0, 1, 1)
    assert r.unmatched == ["Hitwn"]
    assert await _tasks(session) == {}


async def test_archived_goal_does_not_match(session, factory):
    await factory.goal("Old", status=GoalStatus.archived)
    r = await _sync(session, FakeCalendar(timed("e1", "[Old] x")))
    assert r.unmatched == ["Old"] and r.created == 0


async def test_moved_pending_task_follows_its_event(session, factory):
    await factory.goal("A")
    cal = FakeCalendar(timed("e1", "[A] x"))
    await _sync(session, cal)

    cal.events["e1"] = timed("e1", "[A] renamed", "2026-09-24T14:00:00-04:00", "2026-09-24T14:30:00-04:00")
    assert (await _sync(session, cal)).updated == 1
    t = (await _tasks(session))["e1"]
    assert (t.title, t.start_time, t.duration_minutes) == ("renamed", time(14, 0), 30)


async def test_pending_task_moved_to_another_day_is_moved_not_cancelled(session, factory):
    await factory.goal("A")
    cal = FakeCalendar(timed("e1", "[A] x"))
    await _sync(session, cal)

    cal.events["e1"] = timed("e1", "[A] x", "2026-09-28T09:00:00-04:00", "2026-09-28T10:00:00-04:00")
    r = await _sync(session, cal)
    assert r.cancelled == 0
    t = (await _tasks(session))["e1"]
    assert t.status == TaskStatus.pending and t.scheduled_date == date(2026, 9, 28)


async def test_completed_task_is_never_changed_by_the_calendar(session, factory):
    await factory.goal("A")
    cal = FakeCalendar(timed("e1", "[A] x"))
    await _sync(session, cal)
    t = (await _tasks(session))["e1"]
    t.status = TaskStatus.completed
    await session.commit()

    cal.events["e1"] = timed("e1", "[A] moved", "2026-09-24T15:00:00-04:00", "2026-09-24T16:00:00-04:00")
    await _sync(session, cal)
    del cal.events["e1"]
    await _sync(session, cal)

    t = (await _tasks(session))["e1"]
    assert (t.status, t.title, t.start_time) == (TaskStatus.completed, "x", time(9, 0))


async def test_deleted_event_cancels_its_pending_task(session, factory):
    await factory.goal("A")
    cal = FakeCalendar(timed("e1", "[A] x"))
    await _sync(session, cal)

    del cal.events["e1"]
    assert (await _sync(session, cal)).cancelled == 1
    t = (await _tasks(session))["e1"]
    assert t.status == TaskStatus.cancelled and t.cancel_reason is None


async def test_google_unreachable_changes_nothing(session, factory):
    await factory.goal("A")
    cal = FakeCalendar(timed("e1", "[A] x"))
    await _sync(session, cal)

    cal.reachable = False
    assert await _sync(session, cal) is None
    assert (await _tasks(session))["e1"].status == TaskStatus.pending


async def test_all_day_event_imports_with_calendar_length(session, factory):
    await factory.goal("A")
    await _sync(session, FakeCalendar(all_day("e1", "[A] offsite")))
    t = (await _tasks(session))["e1"]
    assert t.is_all_day and t.duration_minutes == 1440 and t.start_time is None


# --- API -----------------------------------------------------------------------


async def test_get_tasks_returns_the_day_with_goal_titles(client, session, factory):
    await factory.goal("Hitwin")
    await _sync(session, FakeCalendar(timed("e1", "[Hitwin] x"), all_day("e2", "[Hitwin] y")))

    r = await client.get("/tasks", params={"date": "2026-09-24"})
    assert r.status_code == 200
    body = r.json()
    assert [t["title"] for t in body] == ["y", "x"], "all-day first"
    assert body[0]["goal_title"] == "Hitwin"
    assert (await client.get("/tasks", params={"date": "2026-09-25"})).json() == []


async def test_sync_endpoint_without_google_is_503(client):
    # conftest blanks GOOGLE_REFRESH_TOKEN, so calendar is disabled in tests.
    assert (await client.post("/tasks/sync")).status_code == 503


async def test_goal_with_tasks_cannot_be_hard_deleted(client, session, factory):
    goal_id = (await factory.goal("A")).id
    await _sync(session, FakeCalendar(timed("e1", "[A] x")))

    r = await client.delete(f"/goals/{goal_id}", params={"hard": "true"})
    assert r.status_code == 409
    assert len(await _tasks(session)) == 1

    # Archiving is still allowed.
    assert (await client.delete(f"/goals/{goal_id}")).status_code == 204
