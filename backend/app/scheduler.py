"""
Background jobs: the 23:59 rep sweep, the 00:00 task sweep, the weekly debrief
email, and the 15-minute calendar → tasks sync.
"""

import logging

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.services.debrief import (
    get_weekly_summary_data,
    generate_debrief_text,
    generate_debrief_audio_bytes,
    store_weekly_summary,
)
from app.services.email import send_debrief_email
from app.services.google_calendar import GoogleCalendarClient
from app.services.task_sweep import sweep_missed_tasks
from app.services.task_sync import sync_tasks
from app.services.sweep import sweep_missed
from app.db.session import AsyncSessionLocal

# Explicit timezone. Without it APScheduler resolves the *host* zone via
# tzlocal — America/New_York on a Mac, UTC in python:3.11-slim — so "Sunday
# 21:00" fired at 21:00 UTC on Railway while looking correct in local dev.
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.tz)


async def send_weekly_debrief():
    """
    Generate and email the weekly debrief every Sunday at 21:00.
    """
    if not settings.email_enabled:
        logger.info("Weekly debrief skipped: email not configured")
        return

    try:
        # Create a temporary session for the job
        engine = create_async_engine(settings.database_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            # Get this week's debrief data
            today = datetime.now(tz=settings.tz).date()
            week_data = await get_weekly_summary_data(session, today, settings.tz)
            summary_text = await generate_debrief_text(week_data)
            audio_bytes = await generate_debrief_audio_bytes(summary_text)

            # Send email
            subject = f"Weekly Debrief: {week_data['week_start']} to {week_data['week_end']}"
            sent = await send_debrief_email(
                recipient=settings.smtp_user,
                subject=subject,
                summary_text=summary_text,
                audio_bytes=audio_bytes,
            )

            # delivered_at distinguishes "generated" from "actually arrived".
            await store_weekly_summary(
                session,
                week_data,
                delivered_at=datetime.now(tz=settings.tz) if sent else None,
            )

        await engine.dispose()

    except Exception:
        logger.exception("Failed to send weekly debrief")


async def run_end_of_day_sweep():
    """
    23:59 local: close out the day. Pending reps for any day that has ended
    become missed and their calendar events turn red.
    """
    try:
        async with AsyncSessionLocal() as session:
            today = datetime.now(tz=settings.tz).date()
            swept = await sweep_missed(session, through=today)
            logger.info("End-of-day sweep marked %s rep(s) missed", swept)
    except Exception:
        # Never let a job exception kill the scheduler thread.
        logger.exception("End-of-day sweep failed")


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


def init_scheduler():
    """Initialize and start the background scheduler."""
    # The sweep is core product behaviour — missed reps must turn red on their
    # own — so it registers regardless of configuration. Only the debrief email
    # depends on SMTP credentials.
    scheduler.add_job(
        run_end_of_day_sweep,
        "cron",
        hour=23,
        minute=59,
        id="end_of_day_sweep",
        replace_existing=True,
    )

    # Like the rep sweep, registered regardless of configuration: marking a task
    # missed is product behaviour, and the calendar colour is only a copy of it.
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

    if settings.email_enabled:
        # Weekly debrief email, Sundays at 21:00 local.
        scheduler.add_job(
            send_weekly_debrief,
            "cron",
            day_of_week=6,  # Sunday
            hour=21,
            minute=0,
            id="weekly_debrief",
            replace_existing=True,
        )
    else:
        logger.warning("Email not configured — weekly debrief job not scheduled")

    scheduler.start()
    # Log the resolved fire times, not the intent. This is the only way to catch
    # a timezone regression without waiting a day or a week to notice.
    for job_id in ("end_of_day_sweep", "task_sweep", "weekly_debrief", "task_sync"):
        job = scheduler.get_job(job_id)
        if job is not None:
            logger.info("Scheduled %s — next run %s", job_id, job.next_run_time)

