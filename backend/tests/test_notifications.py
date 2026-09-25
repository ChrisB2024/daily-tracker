"""
The three scheduled notifications (Build Plan 3, Unit 24). The pure message
builders are tested directly; the senders run against the test database with
send_to_all replaced, so nothing is pushed anywhere.
"""

from datetime import date, time

import pytest

from app.models import Goal, Task, TaskStatus
from app.services import notifications as n

DAY = date(2026, 9, 24)  # a Thursday


def t(goal, title, minutes=60, status=TaskStatus.pending):
    return Task(goal=goal, title=title, duration_minutes=minutes, status=status)


# --- wording --------------------------------------------------------------------------


def test_morning_summary_counts_tasks_time_and_goals():
    hitwin, angle = Goal(title="Hitwin"), Goal(title="Angle")
    title, body = n.morning_summary_message([
        t(hitwin, "a", 90), t(hitwin, "b", 30), t(angle, "c", 60),
        t(angle, "gone", 45, TaskStatus.cancelled),
    ])
    assert title == "Today: 3 tasks · 3h"
    assert body == "Hitwin 2 · Angle 1"


def test_morning_summary_with_an_empty_calendar():
    title, _ = n.morning_summary_message([])
    assert title == "Nothing planned today"


def test_evening_reminder_lists_what_is_unchecked():
    g = Goal(title="Hitwin")
    title, body = n.evening_reminder_message([
        t(g, "ship onboarding"), t(g, "fix bug", status=TaskStatus.completed),
        t(g, "review PRs"), t(g, "changelog"), t(g, "deploy"),
    ])
    assert title == "4 tasks still unchecked"
    assert body == "ship onboarding, review PRs, changelog and 1 more. Tick them before midnight."


def test_evening_reminder_is_silent_when_everything_is_done():
    g = Goal(title="Hitwin")
    assert n.evening_reminder_message([t(g, "x", status=TaskStatus.completed)]) is None
    assert n.evening_reminder_message([]) is None


def test_weekly_recap_ranks_goals_with_completed_time():
    graph = {
        "start_date": date(2026, 9, 21),
        "nodes": [
            {"kind": "goal", "label": "AI", "minutes_completed": 195},
            {"kind": "goal", "label": "Hitwin", "minutes_completed": 180},
            {"kind": "goal", "label": "Angle", "minutes_completed": 0},
            {"kind": "task", "label": "x"},
        ],
    }
    title, body = n.weekly_recap_message(graph)
    assert title == "Week of Sep 21: 6h15 done"
    assert body == "1. AI 3h15 · 2. Hitwin 3h", "goals with nothing done are left out"


def test_weekly_recap_for_an_empty_week():
    title, _ = n.weekly_recap_message({"start_date": date(2026, 9, 21), "nodes": []})
    assert title == "Week of Sep 21: nothing completed"


# --- senders against the database -------------------------------------------------------


@pytest.fixture
def sent(monkeypatch):
    calls = []

    async def fake_send_to_all(session, *, title, body, url="/"):
        calls.append({"title": title, "body": body, "url": url})
        return 1

    monkeypatch.setattr(n, "send_to_all", fake_send_to_all)
    return calls


@pytest.fixture
async def seeded(session, factory):
    hitwin = (await factory.goal("Hitwin")).id
    session.add_all([
        Task(goal_id=hitwin, calendar_event_id="e1", title="ship onboarding", scheduled_date=DAY,
             start_time=time(9), end_time=time(10), duration_minutes=60, status=TaskStatus.pending),
        Task(goal_id=hitwin, calendar_event_id="e2", title="fix bug", scheduled_date=DAY,
             start_time=time(11), end_time=time(12), duration_minutes=60, status=TaskStatus.completed),
    ])
    await session.commit()


async def test_jobs_send_the_expected_messages(session, seeded, sent):
    await n.send_morning_summary(session, DAY)
    await n.send_evening_reminder(session, DAY)
    await n.send_weekly_recap(session, DAY)

    assert [c["title"] for c in sent] == [
        "Today: 2 tasks · 2h",
        "1 task still unchecked",
        "Week of Sep 21: 1h done",
    ]
    assert sent[1]["body"].startswith("ship onboarding.")
    assert sent[2]["url"] == "/?view=week-graph", "the recap opens the week graph"


async def test_evening_job_sends_nothing_when_all_done(session, factory, sent):
    g = (await factory.goal("Hitwin")).id
    session.add(Task(goal_id=g, calendar_event_id="e1", title="x", scheduled_date=DAY,
                     duration_minutes=30, status=TaskStatus.completed))
    await session.commit()

    assert await n.send_evening_reminder(session, DAY) is None
    assert sent == []


def test_notification_jobs_fire_at_the_agreed_times():
    from app.scheduler import NOTIFICATION_JOBS

    when = {job_id: fields for job_id, _, fields in NOTIFICATION_JOBS}
    assert when == {
        "morning_summary": {"hour": 8, "minute": 0},
        "evening_reminder": {"hour": 21, "minute": 0},
        "weekly_recap": {"day_of_week": "sun", "hour": 20, "minute": 0},
    }
