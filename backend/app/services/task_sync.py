"""
Calendar → tasks sync (calendar-first redesign, Unit 15).

Reads the primary Google Calendar for a window of days and makes the `tasks`
table agree with it. Runs every 15 minutes from the scheduler and on demand from
POST /tasks/sync.

The rules, in the order the code applies them:

1. An event carrying `extendedProperties.private.rep_id` was written by the old
   rep system. Skip it — "[Build project] Angle" would otherwise parse as a task
   for a goal called "Build project".
2. An event whose title does not start with "[Something]" is not a task.
   Meetings and personal events never enter the tracker.
3. "[Something]" must name an active goal, case-insensitively. If it does not,
   the prefix is reported back as unmatched rather than silently dropped.
4. A new tagged event becomes a pending task.
5. A moved or renamed event updates its task — **only while the task is
   pending.** Completed, missed and cancelled tasks are evidence; nothing read
   from Google may change them.
6. A pending task whose event is no longer in the window is looked up by id. If
   Google says it was deleted, the task becomes cancelled (Chris writes the
   reason later). If it still exists — moved to another day — the task follows
   it. If Google cannot be reached, nothing changes.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, tzinfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Goal, GoalStatus, Task, TaskStatus

logger = logging.getLogger(__name__)

# "[Hitwin] ship onboarding" → ("Hitwin", "ship onboarding")
PREFIX = re.compile(r"^\s*\[([^\]]+)\]\s*(.*)$")


@dataclass
class ParsedEvent:
    """What a tagged calendar event says, before it is matched to a goal."""

    event_id: str
    goal_tag: str
    title: str
    scheduled_date: date
    start_time: time | None
    end_time: time | None
    is_all_day: bool
    duration_minutes: int


@dataclass
class SyncResult:
    start_date: date
    end_date: date
    synced_at: datetime
    created: int = 0
    updated: int = 0
    cancelled: int = 0
    unchanged: int = 0
    untagged: int = 0
    rep_events_skipped: int = 0
    # Prefixes that named no active goal, e.g. a typo like "[Hitwn]".
    unmatched: list[str] = field(default_factory=list)


def is_rep_event(event: dict) -> bool:
    return "rep_id" in event.get("extendedProperties", {}).get("private", {})


def parse_event(event: dict, tz: tzinfo) -> ParsedEvent | None:
    """
    Turn one Google event into a ParsedEvent, or None if it is not a task.

    Pure function — no database, no network — so it is tested directly.
    """
    if event.get("status") == "cancelled" or is_rep_event(event):
        return None

    match = PREFIX.match(event.get("summary") or "")
    if match is None:
        return None
    goal_tag, title = match.group(1).strip(), match.group(2).strip()

    start, end = event.get("start", {}), event.get("end", {})

    if "date" in start:
        # All-day. Google's end date is exclusive: a one-day event on the 24th
        # ends on the 25th. Duration is the span as the calendar shows it.
        start_day = date.fromisoformat(start["date"])
        end_day = date.fromisoformat(end["date"])
        return ParsedEvent(
            event_id=event["id"],
            goal_tag=goal_tag,
            title=title,
            scheduled_date=start_day,
            start_time=None,
            end_time=None,
            is_all_day=True,
            duration_minutes=(end_day - start_day).days * 24 * 60,
        )

    # Timed. Google returns an offset ("...T09:00:00-04:00"); convert to
    # settings.tz so the date is Chris's date, not the calendar's.
    start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
    end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(tz)
    return ParsedEvent(
        event_id=event["id"],
        goal_tag=goal_tag,
        title=title,
        scheduled_date=start_dt.date(),
        start_time=start_dt.time().replace(tzinfo=None),
        end_time=end_dt.time().replace(tzinfo=None),
        is_all_day=False,
        duration_minutes=int((end_dt - start_dt).total_seconds() // 60),
    )


def _fields(parsed: ParsedEvent, goal: Goal) -> dict:
    """The columns of a task that come from its calendar event."""
    return {
        "goal_id": goal.id,
        "title": parsed.title,
        "scheduled_date": parsed.scheduled_date,
        "start_time": parsed.start_time,
        "end_time": parsed.end_time,
        "is_all_day": parsed.is_all_day,
        "duration_minutes": parsed.duration_minutes,
    }


def _apply(task: Task, parsed: ParsedEvent, goal: Goal) -> bool:
    """Copy the event's current shape onto a pending task. True if anything changed."""
    changed = False
    for name, value in _fields(parsed, goal).items():
        if getattr(task, name) != value:
            setattr(task, name, value)
            changed = True
    return changed


async def sync_tasks(
    session: AsyncSession,
    client,
    start_date: date,
    end_date: date,
    tz: tzinfo,
) -> SyncResult | None:
    """
    Make `tasks` agree with the calendar for start_date..end_date inclusive.

    `client` is a GoogleCalendarClient (tests pass a fake with the same two
    methods). Returns None if Google could not be reached — in that case nothing
    was changed.
    """
    window_start = datetime.combine(start_date, time.min, tzinfo=tz)
    window_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)

    events = await client.list_events(window_start, window_end)
    if events is None:
        return None

    result = SyncResult(
        start_date=start_date, end_date=end_date, synced_at=datetime.now(tz=tz)
    )

    goals_by_tag = {
        g.title.strip().lower(): g
        for g in (
            await session.execute(select(Goal).where(Goal.status == GoalStatus.active))
        ).scalars()
    }

    # Rules 1–3: sort every event into skipped or parsed.
    parsed_events: list[ParsedEvent] = []
    for event in events:
        if is_rep_event(event):
            result.rep_events_skipped += 1
            continue
        parsed = parse_event(event, tz)
        if parsed is None:
            result.untagged += 1
            continue
        # The listing is by overlap, so an event that began yesterday evening
        # shows up today. It belongs to the day it started on.
        if not (start_date <= parsed.scheduled_date <= end_date):
            continue
        parsed_events.append(parsed)

    seen_ids = {p.event_id for p in parsed_events}

    # Every task that could be affected, in one query: tasks for these events
    # (whatever date they currently sit on — the event may have moved in), plus
    # pending tasks in the window (their event may have been deleted).
    conditions = [
        (Task.status == TaskStatus.pending)
        & (Task.scheduled_date >= start_date)
        & (Task.scheduled_date <= end_date)
    ]
    if seen_ids:
        conditions.append(Task.calendar_event_id.in_(seen_ids))
    tasks_by_event = {
        t.calendar_event_id: t
        for t in (await session.execute(select(Task).where(or_(*conditions)))).scalars()
    }

    unmatched: set[str] = set()

    def upsert(parsed: ParsedEvent) -> None:
        goal = goals_by_tag.get(parsed.goal_tag.lower())
        if goal is None:
            unmatched.add(parsed.goal_tag)
            return
        task = tasks_by_event.get(parsed.event_id)
        if task is None:
            # Rule 4
            session.add(
                Task(
                    calendar_event_id=parsed.event_id,
                    status=TaskStatus.pending,
                    **_fields(parsed, goal),
                )
            )
            result.created += 1
        elif task.status != TaskStatus.pending:
            # Rule 5: evidence is never rewritten from Google.
            result.unchanged += 1
        elif _apply(task, parsed, goal):
            result.updated += 1
        else:
            result.unchanged += 1

    for parsed in parsed_events:
        upsert(parsed)

    # Rule 6: pending tasks whose event was not in the listing.
    for event_id, task in tasks_by_event.items():
        if event_id in seen_ids or task.status != TaskStatus.pending:
            continue
        event = await client.get_event(event_id)
        if event is None:
            continue  # unknown — change nothing
        if event.get("status") == "cancelled":
            task.status = TaskStatus.cancelled
            result.cancelled += 1
            continue
        moved = parse_event(event, tz)
        if moved is not None:
            upsert(moved)
        # An event that lost its "[Goal]" prefix is left alone: the task stays
        # pending, and the 00:00 sweep (Unit 16) will judge it like any other.

    result.unmatched = sorted(unmatched)
    await session.commit()

    logger.info(
        "Task sync %s..%s: %s created, %s updated, %s cancelled, %s unmatched",
        start_date,
        end_date,
        result.created,
        result.updated,
        result.cancelled,
        len(result.unmatched),
    )
    return result

