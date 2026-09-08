"""
Weekly debrief generation using Claude API.

Fetches the past week's data, generates a summary via Claude, converts to audio via ElevenLabs.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.models import Rep, RepStatus, RepType, RepTypeStatus, Goal
from sqlalchemy.orm import selectinload

from app.services.summary import (
    week_start_for,
    walk_chain,
    get_week_total,
    get_weekly_pr,
    get_first_rep_rate,
)
from app.config import settings


async def get_weekly_summary_data(session: AsyncSession, target_date: date, tz: ZoneInfo) -> dict:
    """
    Everything the Sunday debrief is supposed to talk about, per readme.md's
    pipeline steps 2-4: per-rep-type chains and how they moved, the week total
    against the all-time PR, the first-rep rate, chains that broke and when, and
    the most-completed and most-avoided rep types.

    Aggregates and titles only — rep `notes` never leave the system
    (architecture.md, security invariant 4).
    """
    # Mon-Sun, the same week the dashboard shows all week. Previously this
    # derived a Sunday-start week of its own, so the Sunday 21:00 debrief
    # reported the *previous* Sun-Sat and excluded the day it ran.
    week_start = week_start_for(target_date)
    week_end = week_start + timedelta(days=7)
    last_day = week_end - timedelta(days=1)
    today = datetime.now(tz).date()
    # A week still in progress is only judged up to today.
    as_of = min(last_day, today)

    stmt = (
        select(Rep)
        .options(selectinload(Rep.rep_type), selectinload(Rep.goal))
        .where(Rep.scheduled_date >= week_start, Rep.scheduled_date < week_end)
    )
    reps = (await session.execute(stmt)).scalars().all()

    # --- per goal, as before -------------------------------------------------
    goals_data: dict = {}
    for rep in reps:
        # Keyed by str, not UUID: the payload has to stay JSON-serialisable —
        # Unit 11 persists it as JSONB, and json.dumps rejects UUID keys.
        g = goals_data.setdefault(
            str(rep.goal_id),
            {"goal_title": rep.goal.title, "completed": 0, "missed": 0, "pending": 0},
        )
        if rep.status == RepStatus.completed:
            g["completed"] += 1
        elif rep.status == RepStatus.missed:
            g["missed"] += 1
        else:
            g["pending"] += 1

    completed_count = sum(1 for r in reps if r.status == RepStatus.completed)
    missed_count = sum(1 for r in reps if r.status == RepStatus.missed)
    total_count = len(reps)

    # --- chains: now, a week ago, and where they broke ------------------------
    rep_types = (
        (
            await session.execute(
                select(RepType)
                .options(selectinload(RepType.goal))
                .where(RepType.status == RepTypeStatus.active)
            )
        )
        .scalars()
        .all()
    )

    # One query for every completion, then walk locally. Asking get_chains for
    # each of the nine dates below would issue a query per rep type per date.
    completions = (
        await session.execute(
            select(Rep.rep_type_id, Rep.scheduled_date).where(
                Rep.status == RepStatus.completed
            )
        )
    ).all()
    dates_by_type: dict = {}
    for rt_id, day in completions:
        dates_by_type.setdefault(rt_id, set()).add(day)

    prev_day = week_start - timedelta(days=1)
    chains, broken = [], []
    for rt in rep_types:
        dates = dates_by_type.get(rt.id, set())
        current = walk_chain(dates, as_of)
        previous = walk_chain(dates, prev_day)
        # "No comparison" is not "no change": a rep type created during the week
        # has no prior chain to compare against.
        existed_before = rt.created_at.astimezone(tz).date() <= prev_day
        chains.append(
            {
                "rep_type_name": rt.name,
                "goal_title": rt.goal.title,
                "current": current,
                "previous": previous if existed_before else None,
                "delta": (current - previous) if existed_before else None,
            }
        )

        # A break is a day the chain fell to zero having been alive the day before.
        day = week_start
        while day <= as_of:
            if walk_chain(dates, day) == 0 and walk_chain(dates, day - timedelta(days=1)) > 0:
                broken.append(
                    {
                        "rep_type_name": rt.name,
                        "goal_title": rt.goal.title,
                        "broke_on": day.isoformat(),
                    }
                )
            day += timedelta(days=1)

    chains.sort(key=lambda c: -c["current"])

    # --- week total against the all-time PR ----------------------------------
    week_total = await get_week_total(session, target_date, tz)
    weekly_pr = await get_weekly_pr(session, tz)
    if weekly_pr == 0:
        pr_status = "no_pr_yet"
    elif week_total > weekly_pr:
        pr_status = "beat"
    elif week_total == weekly_pr:
        pr_status = "matched"
    else:
        pr_status = "below"

    # --- first rep before noon, per goal -------------------------------------
    first_rep_rates = [
        {
            "goal_title": r.goal_title,
            "rate": r.rate,  # None = none scheduled, which is not 0%
            "days_hit": r.days_hit,
            "days_scheduled": r.days_scheduled,
        }
        for r in await get_first_rep_rate(session, target_date, tz)
    ]

    # --- most completed and most avoided -------------------------------------
    completed_by_type: dict = {}
    for rep in reps:
        if rep.status == RepStatus.completed:
            completed_by_type[rep.rep_type_id] = completed_by_type.get(rep.rep_type_id, 0) + 1

    most_completed = None
    if completed_by_type:
        rt_id = max(completed_by_type, key=completed_by_type.get)
        rt = next((x for x in rep_types if x.id == rt_id), None)
        if rt is not None:
            most_completed = {
                "rep_type_name": rt.name,
                "goal_title": rt.goal.title,
                "completed": completed_by_type[rt_id],
            }

    # Ranked by completed-against-expected, not raw count — otherwise a rarely
    # scheduled rep type always looks like the most avoided one.
    ranked = []
    for rt in rep_types:
        if rt.weekly_target:
            expected = rt.weekly_target
        elif rt.daily_floor:
            expected = rt.daily_floor * 7
        else:
            continue  # no stated cadence, so nothing to fall short of
        done = completed_by_type.get(rt.id, 0)
        ranked.append(
            {
                "rep_type_name": rt.name,
                "goal_title": rt.goal.title,
                "completed": done,
                "expected": expected,
                "ratio": round(done / expected, 2),
            }
        )
    most_avoided = min(ranked, key=lambda r: r["ratio"]) if ranked else None

    return {
        "week_start": week_start.isoformat(),
        "week_end": last_day.isoformat(),
        "total_reps": total_count,
        "completed": completed_count,
        "missed": missed_count,
        "goals": goals_data,
        "completion_rate": round((completed_count / total_count * 100) if total_count > 0 else 0, 1),
        "chains": chains,
        "broken_chains": broken,
        "week_total": week_total,
        "weekly_pr": weekly_pr,
        "pr_status": pr_status,
        "first_rep_rates": first_rep_rates,
        "most_completed": most_completed,
        "most_avoided": most_avoided,
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
