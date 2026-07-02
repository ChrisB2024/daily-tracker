"""
Weekly debrief generation using Claude API.

Fetches the past week's data, generates a summary via Claude, converts to audio via ElevenLabs.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.models import Rep, RepStatus, RepType, Goal
from app.config import settings


async def get_weekly_summary_data(session: AsyncSession, target_date: date, tz: ZoneInfo) -> dict:
    """
    Fetch aggregated data for the past week (Sunday-Saturday).

    Returns dict with completed reps by goal, chains, missed reps, etc.
    """
    # Calculate week range (Sunday to Saturday)
    week_start = target_date - timedelta(days=target_date.weekday() + 1)  # Sunday
    week_end = week_start + timedelta(days=7)

    # Get all reps for the week
    stmt = select(Rep).where(
        Rep.scheduled_date >= week_start,
        Rep.scheduled_date < week_end,
    )
    result = await session.execute(stmt)
    reps = result.scalars().all()

    # Eager load rep_type and goal
    for rep in reps:
        await session.refresh(rep, ["rep_type", "goal"])

    # Organize by goal
    goals_data = {}
    for rep in reps:
        goal_id = rep.goal_id
        if goal_id not in goals_data:
            goals_data[goal_id] = {
                "goal_title": rep.goal.title,
                "completed": 0,
                "missed": 0,
                "pending": 0,
            }

        if rep.status == RepStatus.completed:
            goals_data[goal_id]["completed"] += 1
        elif rep.status == RepStatus.missed:
            goals_data[goal_id]["missed"] += 1
        else:
            goals_data[goal_id]["pending"] += 1

    # Calculate week stats
    completed_count = sum(1 for rep in reps if rep.status == RepStatus.completed)
    missed_count = sum(1 for rep in reps if rep.status == RepStatus.missed)
    total_count = len(reps)

    return {
        "week_start": week_start.isoformat(),
        "week_end": (week_end - timedelta(days=1)).isoformat(),
        "total_reps": total_count,
        "completed": completed_count,
        "missed": missed_count,
        "goals": goals_data,
        "completion_rate": round((completed_count / total_count * 100) if total_count > 0 else 0, 1),
    }


async def generate_debrief_text(week_data: dict) -> str:
    """
    Generate a natural debrief summary using Claude.

    Takes week's data and creates a personalized audio-friendly summary.
    """
    if not settings.claude_api_key:
        return "Debrief feature not configured. Add CLAUDE_API_KEY to .env"

    from anthropic import Anthropic

    try:
        client = Anthropic(api_key=settings.claude_api_key)
    except Exception as e:
        return f"Failed to initialize Claude: {str(e)}"

    # Build context for Claude
    goals_summary = "\n".join(
        [
            f"- {goal['goal_title']}: {goal['completed']} completed, {goal['missed']} missed"
            for goal in week_data["goals"].values()
        ]
    )

    prompt = f"""
You are a personal coach giving a brief, encouraging weekly debrief. Based on this week's data, write a 2-3 sentence audio-friendly summary that:
1. Acknowledges progress (completed reps, completion rate)
2. Mentions any patterns or wins
3. Is conversational and motivating (for text-to-speech)

Keep it natural and spoken, not written. No bullet points or technical language.

Week: {week_data['week_start']} to {week_data['week_end']}
Total reps: {week_data['total_reps']}
Completed: {week_data['completed']}
Missed: {week_data['missed']}
Completion rate: {week_data['completion_rate']}%

Goals this week:
{goals_summary}

Write the debrief summary now:
"""

    try:
        message = await asyncio.to_thread(
            lambda: client.messages.create(
                model="claude-opus-4-8",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
        )
        return message.content[0].text
    except Exception as e:
        return f"Failed to generate summary: {str(e)}"


async def generate_debrief_audio_bytes(text: str) -> bytes:
    """
    Convert debrief text to audio bytes using ElevenLabs.

    Returns raw audio bytes (for email attachment). Audio is optional.
    """
    if not settings.elevenlabs_api_key:
        return b""

    try:
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=settings.elevenlabs_api_key)

        audio_generator = await asyncio.to_thread(
            lambda: client.text_to_speech.convert(
                voice_id="21m00Tcm4TlvDq8ikWAM",
                text=text,
                model_id="eleven_turbo_v2_5",
            )
        )

        return b"".join(audio_generator)
    except Exception:
        return b""


async def generate_debrief_audio(text: str) -> str:
    """
    Convert debrief text to audio using ElevenLabs.

    Returns base64-encoded audio data.
    """
    if not settings.elevenlabs_api_key:
        return ""

    try:
        from elevenlabs.client import ElevenLabs
        import base64

        client = ElevenLabs(api_key=settings.elevenlabs_api_key)

        audio_generator = await asyncio.to_thread(
            lambda: client.text_to_speech.convert(
                voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel voice ID
                text=text,
                model_id="eleven_turbo_v2_5",
            )
        )

        # Collect audio chunks into bytes
        audio_bytes = b"".join(audio_generator)
        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception:
        return ""


async def get_debrief(session: AsyncSession, target_date: date, tz: ZoneInfo) -> dict:
    """
    Generate complete weekly debrief with text and audio.
    """
    week_data = await get_weekly_summary_data(session, target_date, tz)
    summary_text = await generate_debrief_text(week_data)
    audio_data = await generate_debrief_audio(summary_text)

    return {
        "week_start": week_data["week_start"],
        "week_end": week_data["week_end"],
        "summary": summary_text,
        "audio_base64": audio_data,
        "stats": {
            "completed": week_data["completed"],
            "missed": week_data["missed"],
            "total": week_data["total_reps"],
            "completion_rate": week_data["completion_rate"],
        },
    }
