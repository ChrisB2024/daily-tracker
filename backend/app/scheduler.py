"""
Background jobs: the 00:00 task sweep, the 15-minute calendar → tasks sync,
and — when push is configured — three notifications (Build Plan 3, Unit 24):
08:00 morning summary, 21:00 evening reminder, Sunday 20:00 weekly recap.

The 23:59 rep sweep and the Sunday debrief email were retired in Unit 20 of the
calendar-first redesign. Their services still exist — POST /reps/mark-missed
and GET /debrief call them — they are just no longer run on a timer.
"""

import logging

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services.google_calendar import GoogleCalendarClient
from app.services.notifications import (
    send_evening_reminder,
    send_morning_summary,
    send_weekly_recap,
)
from app.services.task_sweep import sweep_missed_tasks
from app.services.task_sync import sync_tasks
from app.db.session import AsyncSessionLocal

# Explicit timezone. Without it APScheduler resolves the *host* zone via
# tzlocal — America/New_York on a Mac, UTC in python:3.11-slim — so "00:00"
# would fire at midnight UTC on Railway while looking correct in local dev.
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.tz)


async def run_task_sweep():
    """
    00:00 local: yesterday is over. Its unchecked tasks become missed and their
    calendar events turn red.
    """
    try:
        async with AsyncSessionLocal() as session:
            yesterday = datetime.now(tz=settings.tz).date() - timedelta(days=1)
            await sweep_missed_tasks(session, through=yesterday)
    except Exception:
        logger.exception("Task sweep failed")


async def run_task_sync():
    """
    Every 15 minutes: pull today's and tomorrow's tagged events into tasks.
    Tomorrow is included so an evening of planning shows up before midnight.
    """
    try:
        client = GoogleCalendarClient(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
        )
        async with AsyncSessionLocal() as session:
            today = datetime.now(tz=settings.tz).date()
            result = await sync_tasks(
                session, client, today, today + timedelta(days=1), settings.tz
            )
            if result is None:
                logger.error("Task sync skipped: Google Calendar unreachable")
    except Exception:
        logger.exception("Task sync failed")


def _notification_job(send):
    """Wrap a services/notifications.py sender as a job with its own session."""

    async def job():
        try:
            async with AsyncSessionLocal() as session:
                await send(session, datetime.now(tz=settings.tz).date())
        except Exception:
            logger.exception("Notification job %s failed", send.__name__)

    job.__name__ = f"run_{send.__name__}"
    return job


NOTIFICATION_JOBS = (
    # (id, sender, cron fields in settings.tz)
    ("morning_summary", send_morning_summary, {"hour": 8, "minute": 0}),
    ("evening_reminder", send_evening_reminder, {"hour": 21, "minute": 0}),
    ("weekly_recap", send_weekly_recap, {"day_of_week": "sun", "hour": 20, "minute": 0}),
)


def init_scheduler():
    """Initialize and start the background scheduler."""
    # Registered regardless of configuration: marking a task missed is product
    # behaviour, and the calendar colour is only a copy of it.
    scheduler.add_job(
        run_task_sweep,
        "cron",
        hour=0,
        minute=0,
        id="task_sweep",
        replace_existing=True,
    )

    if settings.google_calendar_enabled:
        scheduler.add_job(
            run_task_sync,
            "interval",
            minutes=15,
            id="task_sync",
            replace_existing=True,
            # A slow Google response must not stack a second run on the first.
            max_instances=1,
            coalesce=True,
        )
    else:
        logger.warning("Google Calendar not configured — task sync job not scheduled")

    if settings.push_enabled:
        for job_id, send, when in NOTIFICATION_JOBS:
            scheduler.add_job(
                _notification_job(send), "cron", id=job_id, replace_existing=True, **when
            )
    else:
        logger.warning("Push not configured — notification jobs not scheduled")

    scheduler.start()
    # Log the resolved fire times, not the intent. This is the only way to catch
    # a timezone regression without waiting a day or a week to notice.
    for job_id in ("task_sweep", "task_sync", *(j[0] for j in NOTIFICATION_JOBS)):
        job = scheduler.get_job(job_id)
        if job is not None:
            logger.info("Scheduled %s — next run %s", job_id, job.next_run_time)

