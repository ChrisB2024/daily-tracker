"""
End-of-day sweep: pending reps on days that have ended become missed.

One implementation shared by the 23:59 cron and the manual endpoint, so the two
cannot drift apart on what "ended" means.
"""

import logging
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Rep, RepStatus
from app.services.google_calendar import GoogleCalendarClient

logger = logging.getLogger(__name__)

MISSED_COLOR_ID = 11  # Tomato (red), per the calendar mapping in readme.md


async def sweep_missed(session: AsyncSession, *, through: date) -> int:
    """
    Mark every pending rep scheduled on or before `through` as missed, and patch
    its calendar event red.

    `through` is the last day that has **ended**:
      - the 23:59 cron passes today, because the day is over
      - the manual endpoint passes yesterday, because today is still open

    Using `<= through` rather than an exact day makes the sweep self-healing:
    APScheduler does not backfill a missed fire, so a restart spanning 23:59
    would otherwise strand that day's reps as pending forever.

    Returns the number of reps marked missed.
    """
    # Collect event ids before the update, while the rows still match the filter.
    event_ids = (
        (
            await session.execute(
                select(Rep.calendar_event_id).where(
                    Rep.status == RepStatus.pending,
                    Rep.scheduled_date <= through,
                    Rep.calendar_event_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )

    result = await session.execute(
        update(Rep)
        .where(Rep.status == RepStatus.pending, Rep.scheduled_date <= through)
        .values(status=RepStatus.missed)
    )
    await session.commit()
    swept = result.rowcount or 0

    if settings.google_calendar_enabled and event_ids:
        # One client for the whole batch — building one per event would refresh
        # the OAuth token once per rep.
        client = GoogleCalendarClient(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
        )
        for event_id in event_ids:
            await client.patch_color(event_id, MISSED_COLOR_ID)

    logger.info("Swept %s rep(s) to missed through %s", swept, through)
    return swept
