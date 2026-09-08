"""
Background scheduler for weekly debrief emails.
"""

from datetime import datetime, date
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.services.debrief import get_weekly_summary_data, generate_debrief_text, generate_debrief_audio_bytes
from app.services.email import send_debrief_email

# Explicit timezone. Without it APScheduler resolves the *host* zone via
# tzlocal — America/New_York on a Mac, UTC in python:3.11-slim — so "Sunday
# 21:00" fired at 21:00 UTC on Railway while looking correct in local dev.
scheduler = AsyncIOScheduler(timezone=settings.tz)


async def send_weekly_debrief():
    """
    Generate and email the weekly debrief every Sunday at 21:00.
    """
    if not settings.email_enabled:
        print("Weekly debrief email skipped: email not configured")
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
            await send_debrief_email(
                recipient=settings.smtp_user,
                subject=subject,
                summary_text=summary_text,
                audio_bytes=audio_bytes,
            )

        await engine.dispose()

    except Exception as e:
        print(f"Failed to send weekly debrief: {e}")


def init_scheduler():
    """Initialize and start the background scheduler."""
    if not settings.email_enabled:
        print("Scheduler: email not configured, skipping weekly debrief job")
        return

    # Schedule debrief email for every Sunday at 21:00
    scheduler.add_job(
        send_weekly_debrief,
        "cron",
        day_of_week=6,  # Sunday
        hour=21,
        minute=0,
        id="weekly_debrief",
        replace_existing=True,
    )

    scheduler.start()
    job = scheduler.get_job("weekly_debrief")
    # Print the resolved fire time, not the intent. This is the only way to catch
    # a timezone regression without waiting a week for a late email.
    print(f"✓ Scheduler started: weekly debrief next runs {job.next_run_time}")
