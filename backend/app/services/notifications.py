"""
The three scheduled notifications (Build Plan 3, Unit 24).

    morning summary    08:00    what is on the calendar today
    evening reminder   21:00    tasks still unchecked — only sent if there are any
    weekly recap       Sun 20:00  the week's goals ranked by time completed

Each has a pure `*_message` function that turns data into (title, body) — or
None for "send nothing" — so the wording is tested without a database or a
phone. The `send_*` functions load the data and hand the message to
services/push.py.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Task, TaskStatus
from app.services.push import send_to_all
from app.services.summary import week_start_for
from app.services.task_graph import get_task_graph

Message = tuple[str, str]

# Where tapping each notification lands. Dashboard reads ?view= on load.
TODAY_URL = "/"
WEEK_GRAPH_URL = "/?view=week-graph"


def format_minutes(minutes: int) -> str:
    """90 → "1h30", 45 → "45m", 120 → "2h" — the same format as the frontend."""
    h, m = divmod(minutes, 60)
    if h == 0:
        return f"{m}m"
    return f"{h}h" if m == 0 else f"{h}h{m:02d}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _list_titles(titles: list[str], limit: int = 3) -> str:
    shown = ", ".join(titles[:limit])
    extra = len(titles) - limit
    return f"{shown} and {extra} more" if extra > 0 else shown


# --- pure message builders ---------------------------------------------------------


def morning_summary_message(tasks: list[Task]) -> Message:
    planned = [t for t in tasks if t.status != TaskStatus.cancelled]
    if not planned:
        return (
            "Nothing planned today",
            "Add events titled [Goal] … to your calendar and they'll show up here.",
        )
    minutes = sum(t.duration_minutes for t in planned)
    per_goal = Counter(t.goal.title for t in planned)
    goals = " · ".join(f"{title} {n}" for title, n in per_goal.most_common())
    return (f"Today: {_plural(len(planned), 'task')} · {format_minutes(minutes)}", goals)


def evening_reminder_message(tasks: list[Task]) -> Message | None:
    pending = [t for t in tasks if t.status == TaskStatus.pending]
    if not pending:
        return None  # everything is ticked (or nothing was planned): stay quiet
    return (
        f"{_plural(len(pending), 'task')} still unchecked",
        f"{_list_titles([t.title for t in pending])}. Tick them before midnight.",
    )


def weekly_recap_message(graph: dict) -> Message:
    goals = [n for n in graph["nodes"] if n["kind"] == "goal"]
    done = sum(g["minutes_completed"] for g in goals)
    start = graph["start_date"]
    week_of = f"{start:%b} {start.day}"  # "Sep 21"; %-d is not portable
    if done == 0:
        return (f"Week of {week_of}: nothing completed", "No tasks were checked off this week.")
    ranked = [g for g in goals if g["minutes_completed"] > 0]  # already most-time-first
    body = " · ".join(
        f"{i}. {g['label']} {format_minutes(g['minutes_completed'])}"
        for i, g in enumerate(ranked, start=1)
    )
    return (f"Week of {week_of}: {format_minutes(done)} done", body)


# --- jobs --------------------------------------------------------------------------


async def _tasks_on(session: AsyncSession, day: date) -> list[Task]:
    return list(
        (
            await session.execute(
                select(Task)
                .where(Task.scheduled_date == day)
                .options(selectinload(Task.goal))
                .order_by(Task.start_time.asc().nulls_first(), Task.title)
            )
        ).scalars()
    )


async def send_morning_summary(session: AsyncSession, today: date) -> Message:
    title, body = morning_summary_message(await _tasks_on(session, today))
    await send_to_all(session, title=title, body=body, url=TODAY_URL)
    return title, body


async def send_evening_reminder(session: AsyncSession, today: date) -> Message | None:
    message = evening_reminder_message(await _tasks_on(session, today))
    if message is not None:
        await send_to_all(session, title=message[0], body=message[1], url=TODAY_URL)
    return message


async def send_weekly_recap(session: AsyncSession, today: date) -> Message:
    monday = week_start_for(today)
    graph = await get_task_graph(session, monday, monday + timedelta(days=6))
    title, body = weekly_recap_message(graph)
    await send_to_all(session, title=title, body=body, url=WEEK_GRAPH_URL)
    return title, body
