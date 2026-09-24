"""
Midnight sweep for tasks (calendar-first redesign, Unit 16).

At 00:00 in settings.tz, every task still pending on a day that has ended
becomes missed, and its calendar event turns red. Chris checks tasks off until
midnight; after that, an unchecked task is a missed one.

Kept apart from services/sweep.py, which sweeps reps at 23:59. The rep sweep
retires in Unit 20; this one stays.
"""

import logging
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Task, TaskStatus
from app.services.google_calendar import GoogleCalendarClient

logger = logging.getLogger(__name__)

MISSED_COLOR_ID = 11  # Tomato (red) — same colour a missed rep gets


async def sweep_missed_tasks(session: AsyncSession, *, through: date) -> int:
    """
    Mark every pending task scheduled on or before `through` as missed, and
    patch its calendar event red. Returns how many were marked.

    `through` is the last day that has ended — the 00:00 job passes yesterday.
    `<=` rather than `==` makes it self-healing: APScheduler does not re-run a
    job it missed, so if the server was down at midnight, the next run still
    catches the stranded day.
    """
    stale = (Task.status == TaskStatus.pending) & (Task.scheduled_date <= through)

    # Collect the event ids first, while the rows still match the filter.
    event_ids = (await session.execute(select(Task.calendar_event_id).where(stale))).scalars().all()

    result = await session.execute(update(Task).where(stale).values(status=TaskStatus.missed))
    # The database first, then Google: the evidence is recorded even if the
    # calendar is unreachable.
    await session.commit()
    swept = result.rowcount or 0

    if settings.google_calendar_enabled and event_ids:
        client = GoogleCalendarClient(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
        )
        for event_id in event_ids:
            await client.patch_color(event_id, MISSED_COLOR_ID)

    logger.info("Swept %s task(s) to missed through %s", swept, through)
    return swept
