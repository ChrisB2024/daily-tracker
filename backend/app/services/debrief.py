"""
Weekly debrief generation using Claude API.

Fetches the past week's data, generates a summary via Claude, converts to audio via ElevenLabs.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import logging

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

logger = logging.getLogger(__name__)


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


def _format_week(w: dict) -> str:
    """Render the payload as plain lines for the prompt. Data only, no framing."""
    lines = [
        f"Week: {w['week_start']} to {w['week_end']}",
        f"Reps completed: {w['completed']} of {w['total_reps']} scheduled ({w['missed']} missed, {w['completion_rate']}% completion)",
        f"Weekly total: {w['week_total']}. All-time PR: {w['weekly_pr']}. This week: {w['pr_status']}.",
        "",
        "Chains (current, previous week, change):",
    ]
    if w["chains"]:
        for c in w["chains"]:
            prev = "no prior week" if c["previous"] is None else f"was {c['previous']}"
            delta = "" if c["delta"] is None else f", {c['delta']:+d}"
            lines.append(
                f"  {c['rep_type_name']} ({c['goal_title']}): {c['current']} days, {prev}{delta}"
            )
    else:
        lines.append("  none")

    lines.append("")
    if w["broken_chains"]:
        lines.append("Chains that broke this week:")
        for b in w["broken_chains"]:
            lines.append(f"  {b['rep_type_name']} ({b['goal_title']}) broke on {b['broke_on']}")
    else:
        lines.append("No chains broke this week.")

    lines.append("")
    lines.append("First rep before noon, per goal:")
    if w["first_rep_rates"]:
        for r in w["first_rep_rates"]:
            if r["days_scheduled"] == 0:
                lines.append(f"  {r['goal_title']}: no first rep scheduled this week")
            else:
                lines.append(
                    f"  {r['goal_title']}: {r['days_hit']} of {r['days_scheduled']} scheduled days"
                    f" ({round(r['rate'] * 100)}%)"
                )
    else:
        lines.append("  no rep type is flagged as a first rep")

    lines.append("")
    if w["most_completed"]:
        m = w["most_completed"]
        lines.append(f"Most completed: {m['rep_type_name']} ({m['goal_title']}), {m['completed']} reps")
    if w["most_avoided"]:
        a = w["most_avoided"]
        lines.append(
            f"Most avoided: {a['rep_type_name']} ({a['goal_title']}), "
            f"{a['completed']} of {a['expected']} expected"
        )

    lines.append("")
    lines.append("Per goal:")
    for g in w["goals"].values():
        lines.append(
            f"  {g['goal_title']}: {g['completed']} completed, {g['missed']} missed, {g['pending']} pending"
        )
    return "\n".join(lines)


# Written to be spoken aloud, so no markdown, no lists, no headers. The worked
# example is readme.md's own target output and carries the voice better than any
# description of it would.
DEBRIEF_SYSTEM = """You write one weekly debrief for Chris, who tracks his work as binary reps \
tagged to goals. You have been watching the numbers all week. You are not a coach and not an app.

Report findings. Chains, numbers, patterns, and what they imply. Nothing else.

Rules, all absolute:
- Do not congratulate, encourage, reassure, or motivate. No "great job", no "keep it up", no "you've got this".
- No emoji. No exclamation marks. No motivational quotes.
- Every sentence must depend on the numbers. If a sentence would read the same with different data, delete it.
- Name specific rep types, goals and figures. Never "some goals" or "a few reps".
- Plain spoken prose. No markdown, no bullet points, no headings — this is read aloud.
- Do not invent data. If something is not in the numbers, do not claim it.
- End with one question that names a specific rep and a specific goal.

This is the target voice and length:

Chris - weekly total: 23 reps. Below your PR of 28 but above floor (15).

Chains: Outbound rep at 6 days, longest this quarter. Session rep at 12 days, matched PR. Build rep broken Tuesday, restarted Wednesday - back to 4 days. Skill rep broken Thursday, not yet restarted.

First-rep-before-noon rate: 5/7 days (71%). The two days you missed the first rep, total reps for that day were 1 and 2. Pattern confirmed: starting predicts the day.

Most-completed: Session rep (5/5). Most-avoided: Outbound rep on the PlumbLine goal - 2 of 5 targeted days, third week below floor. Pattern is consistent.

Worth asking: what is the first PlumbLine rep, and why isn't it happening before noon?"""

DEBRIEF_UNAVAILABLE = "This week's debrief could not be generated."


async def generate_debrief_text(week_data: dict) -> str:
    """
    Turn the week's numbers into findings.

    readme.md forbids the encouraging register outright: "No motivational quotes.
    No emojis. No 'great job!' - just findings, chains, numbers, and patterns."
    "The Sunday debrief feels generic" is a stated V1-failure condition.
    """
    if not settings.claude_api_key:
        return "Debrief feature not configured. Add CLAUDE_API_KEY to .env"

    from anthropic import Anthropic

    try:
        client = Anthropic(api_key=settings.claude_api_key)
        message = await asyncio.to_thread(
            lambda: client.messages.create(
                model="claude-opus-5",
                max_tokens=2000,
                # Pattern analysis over a week of behaviour, not formatting. This
                # runs once a week in a background job — the cheapest place in the
                # system to spend latency and tokens.
                thinking={"type": "adaptive"},
                system=DEBRIEF_SYSTEM,
                messages=[{"role": "user", "content": _format_week(week_data)}],
            )
        )
    except Exception:
        # Never surface the exception text: an auth failure's message is exactly
        # the kind of thing that would put a key fragment into an email.
        logger.exception("Debrief generation failed")
        return DEBRIEF_UNAVAILABLE

    if message.stop_reason == "refusal":
        logger.error("Debrief refused: %s", getattr(message, "stop_details", None))
        return DEBRIEF_UNAVAILABLE
    if message.stop_reason == "max_tokens":
        logger.warning("Debrief hit max_tokens — output truncated")

    text = "".join(b.text for b in message.content if b.type == "text").strip()
    return text or DEBRIEF_UNAVAILABLE


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
