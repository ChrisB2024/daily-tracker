"""
Dashboard summary computations.

All metrics (chains, scores, PRs, first-rep rate) computed at read time from reps table.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rep, RepStatus, RepType, Goal


async def get_daily_score(session: AsyncSession, target_date: date, tz: ZoneInfo) -> int:
    stmt = select(Rep).where(
        Rep.scheduled_date == target_date,
        Rep.status == RepStatus.completed,
    )
    result = await session.execute(stmt)
    return len(result.scalars().all())


async def get_week_total(session: AsyncSession, target_date: date, tz: ZoneInfo) -> int:
    week_start = target_date - timedelta(days=target_date.weekday())
    week_end = week_start + timedelta(days=7)

    stmt = select(Rep).where(
        Rep.scheduled_date >= week_start,
        Rep.scheduled_date < week_end,
        Rep.status == RepStatus.completed,
    )
    result = await session.execute(stmt)
    return len(result.scalars().all())


async def get_weekly_pr(session: AsyncSession, tz: ZoneInfo) -> int:
    stmt = select(Rep).where(Rep.status == RepStatus.completed).order_by(Rep.scheduled_date)
    result = await session.execute(stmt)
    completed_reps = result.scalars().all()

    if not completed_reps:
        return 0

    # Group by week, compute totals
    week_totals = {}
    for rep in completed_reps:
        week_start = rep.scheduled_date - timedelta(days=rep.scheduled_date.weekday())
        week_totals[week_start] = week_totals.get(week_start, 0) + 1

    return max(week_totals.values()) if week_totals else 0


async def get_first_rep_rate(session: AsyncSession, target_date: date, tz: ZoneInfo) -> float:
    week_start = target_date - timedelta(days=target_date.weekday())

    # Get all rep types marked as first-rep
    stmt = select(RepType).where(RepType.is_first_rep == True)
    result = await session.execute(stmt)
    first_rep_types = result.scalars().all()

    if not first_rep_types:
        return 0.0

    # For each day in the week, check if all first-reps were completed before noon
    days_with_all_first_reps = 0
    for day_offset in range(7):
        current_day = week_start + timedelta(days=day_offset)
        all_completed_before_noon = True

        for rep_type in first_rep_types:
            stmt = select(Rep).where(
                Rep.rep_type_id == rep_type.id,
                Rep.scheduled_date == current_day,
                Rep.status == RepStatus.completed,
                Rep.scheduled_time < time(12, 0),
            )
            result = await session.execute(stmt)
            if not result.scalars().first():
                all_completed_before_noon = False
                break

        if all_completed_before_noon:
            days_with_all_first_reps += 1

    return days_with_all_first_reps / 7


class ChainInfo:
    """Per-rep-type chain metadata."""

    def __init__(
        self,
        rep_type_id: str,
        rep_type_name: str,
        goal_id: str,
        goal_title: str,
        current_chain: int,
        last_completed_date: date | None,
    ):
        self.rep_type_id = rep_type_id
        self.rep_type_name = rep_type_name
        self.goal_id = goal_id
        self.goal_title = goal_title
        self.current_chain = current_chain
        self.last_completed_date = last_completed_date


async def get_chains(session: AsyncSession, tz: ZoneInfo) -> list[ChainInfo]:
    stmt = select(RepType)
    result = await session.execute(stmt)
    rep_types = result.scalars().all()

    chains = []
    today = datetime.now(tz).date()

    for rep_type in rep_types:
        # Get all completed reps of this type
        stmt = select(Rep).where(
            Rep.rep_type_id == rep_type.id,
            Rep.status == RepStatus.completed,
        )
        result = await session.execute(stmt)
        completed_reps = result.scalars().all()

        if not completed_reps:
            continue

        # Create set of dates with at least one completion
        dates_completed = {rep.scheduled_date for rep in completed_reps}

        # Walk backwards from today, counting consecutive days with completions
        chain_length = 0
        current_day = today
        while current_day in dates_completed:
            chain_length += 1
            current_day -= timedelta(days=1)

        # Get last completed date
        last_completed_date = max(dates_completed) if dates_completed else None

        # Eagerly load goal
        await session.refresh(rep_type, ["goal"])

        chain = ChainInfo(
            rep_type_id=str(rep_type.id),
            rep_type_name=rep_type.name,
            goal_id=str(rep_type.goal_id),
            goal_title=rep_type.goal.title,
            current_chain=chain_length,
            last_completed_date=last_completed_date,
        )
        chains.append(chain)

    return chains


async def get_chain_history(
    session: AsyncSession, rep_type_id: str, tz: ZoneInfo, days: int = 60
) -> list[dict]:
    """
    Get daily chain progression for a rep_type over the past N days.

    Returns list of dicts with 'date' (ISO string) and 'chain_count'.
    When a day is missed, chain_count resets to 0.
    """
    today = datetime.now(tz).date()
    start_date = today - timedelta(days=days)

    stmt = select(Rep).where(
        Rep.rep_type_id == rep_type_id,
        Rep.scheduled_date >= start_date,
        Rep.scheduled_date <= today,
        Rep.status == RepStatus.completed,
    )
    result = await session.execute(stmt)
    completed_reps = result.scalars().all()

    # Set of dates with at least one completion
    completed_dates = {rep.scheduled_date for rep in completed_reps}

    # Walk through days, computing chain count
    history = []
    chain_count = 0
    current = start_date
    while current <= today:
        if current in completed_dates:
            chain_count += 1
        else:
            chain_count = 0
        history.append({"date": current.isoformat(), "chain_count": chain_count})
        current += timedelta(days=1)

    return history


async def get_goal_progression(
    session: AsyncSession, goal_id: str, tz: ZoneInfo, days: int = 60
) -> list[dict]:
    """
    Get daily progression for a goal over the past N days.

    Cumulative: +1 for completed rep, -1 for missed rep.
    Returns list of dicts with 'date' (ISO string) and 'cumulative_count'.
    """
    today = datetime.now(tz).date()
    start_date = today - timedelta(days=days)

    # Get all reps for this goal in the date range
    stmt = select(Rep).where(
        Rep.goal_id == goal_id,
        Rep.scheduled_date >= start_date,
        Rep.scheduled_date <= today,
    )
    result = await session.execute(stmt)
    reps = result.scalars().all()

    # Group reps by date and status
    daily_reps = {}
    for rep in reps:
        if rep.scheduled_date not in daily_reps:
            daily_reps[rep.scheduled_date] = {"completed": 0, "missed": 0}
        if rep.status == RepStatus.completed:
            daily_reps[rep.scheduled_date]["completed"] += 1
        elif rep.status == RepStatus.missed:
            daily_reps[rep.scheduled_date]["missed"] += 1

    # Walk through days, computing cumulative count
    history = []
    cumulative = 0
    current = start_date
    while current <= today:
        if current in daily_reps:
            cumulative += daily_reps[current]["completed"]
            cumulative -= daily_reps[current]["missed"]
        history.append({"date": current.isoformat(), "cumulative_count": cumulative})
        current += timedelta(days=1)

    return history


async def get_goal_progression_alltime(
    session: AsyncSession, goal_id: str, start_date: date, tz: ZoneInfo
) -> list[dict]:
    """
    Get daily progression for a goal from start_date to today (all-time).

    Cumulative: +1 for completed rep, -1 for missed rep.
    Returns list of dicts with 'date' (ISO string) and 'cumulative_count'.
    """
    today = datetime.now(tz).date()

    # Get all reps for this goal from start_date onwards
    stmt = select(Rep).where(
        Rep.goal_id == goal_id,
        Rep.scheduled_date >= start_date,
        Rep.scheduled_date <= today,
    )
    result = await session.execute(stmt)
    reps = result.scalars().all()

    # Group reps by date and status
    daily_reps = {}
    for rep in reps:
        if rep.scheduled_date not in daily_reps:
            daily_reps[rep.scheduled_date] = {"completed": 0, "missed": 0}
        if rep.status == RepStatus.completed:
            daily_reps[rep.scheduled_date]["completed"] += 1
        elif rep.status == RepStatus.missed:
            daily_reps[rep.scheduled_date]["missed"] += 1

    # Walk through days, computing cumulative count
    history = []
    cumulative = 0
    current = start_date
    while current <= today:
        if current in daily_reps:
            cumulative += daily_reps[current]["completed"]
            cumulative -= daily_reps[current]["missed"]
        history.append({"date": current.isoformat(), "cumulative_count": cumulative})
        current += timedelta(days=1)

    return history


async def get_30day_rhythm(session: AsyncSession, tz: ZoneInfo) -> dict:
    """
    Get daily completion counts for the current calendar month (full month, day 1 to last day).

    Returns a dict with date -> completion_count mapping.
    """
    today = datetime.now(tz).date()
    # Start from first day of current month
    start_date = today.replace(day=1)
    # End on last day of month: get first day of next month, subtract 1 day
    if today.month == 12:
        last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    stmt = select(Rep).where(
        Rep.scheduled_date >= start_date,
        Rep.scheduled_date <= last_day,
        Rep.status == RepStatus.completed,
    )
    result = await session.execute(stmt)
    completed_reps = result.scalars().all()

    # Count completions per day
    daily_counts = {}
    for rep in completed_reps:
        daily_counts[rep.scheduled_date] = daily_counts.get(rep.scheduled_date, 0) + 1

    # Fill in all days of the month with 0
    rhythm = {}
    current = start_date
    while current <= last_day:
        rhythm[current.isoformat()] = daily_counts.get(current, 0)
        current += timedelta(days=1)

    return rhythm


async def get_today_reps(session: AsyncSession, target_date: date) -> list:
    stmt = (
        select(Rep)
        .where(Rep.scheduled_date == target_date)
        .order_by(Rep.scheduled_time)
    )
    result = await session.execute(stmt)
    reps = result.scalars().all()

    # Eager-load rep_type and goal
    for rep in reps:
        await session.refresh(rep, ["rep_type", "goal"])

    # Group by goal
    goals_dict = {}
    for rep in reps:
        goal_id = rep.goal_id
        if goal_id not in goals_dict:
            goals_dict[goal_id] = {
                "goal_id": rep.goal_id,
                "goal_title": rep.goal.title,
                "reps": [],
            }

        goals_dict[goal_id]["reps"].append(
            {
                "rep_id": rep.id,
                "rep_type_name": rep.rep_type.name,
                "scheduled_time": rep.scheduled_time.isoformat(),
                "status": rep.status.value,
                "completed_at": rep.completed_at.isoformat() if rep.completed_at else None,
                "duration_minutes": rep.duration_minutes,
            }
        )

    return list(goals_dict.values())


async def get_rep_type_analytics(session: AsyncSession) -> list[dict]:
    """
    Get completion analytics for all rep types.

    Returns list of dicts with rep_type_id, rep_type_name, goal_title, total_reps, completed_count, missed_count, completion_pct.
    """
    # Get all rep types with their goals
    stmt = select(RepType)
    result = await session.execute(stmt)
    rep_types = result.scalars().all()

    analytics = []
    for rep_type in rep_types:
        # Fetch goal for this rep type
        await session.refresh(rep_type, ["goal"])

        # Count all reps for this rep type
        stmt = select(Rep).where(Rep.rep_type_id == rep_type.id)
        result = await session.execute(stmt)
        all_reps = result.scalars().all()

        total = len(all_reps)
        if total == 0:
            continue

        completed = len([r for r in all_reps if r.status == RepStatus.completed])
        missed = len([r for r in all_reps if r.status == RepStatus.missed])
        completion_pct = int((completed / total) * 100) if total > 0 else 0

        analytics.append({
            "rep_type_id": str(rep_type.id),
            "rep_type_name": rep_type.name,
            "goal_id": str(rep_type.goal_id),
            "goal_title": rep_type.goal.title,
            "total_reps": total,
            "completed_count": completed,
            "missed_count": missed,
            "pending_count": total - completed - missed,
            "completion_pct": completion_pct,
        })

    # Sort by completion % descending
    analytics.sort(key=lambda x: x["completion_pct"], reverse=True)
    return analytics


async def get_week_reps(session: AsyncSession, target_date: date, tz: ZoneInfo) -> dict:
    """
    Get all reps for the week containing target_date, grouped by day.

    Returns dict with week_start date and list of days (Mon-Sun), each with goal groups and reps.
    """
    # Get week start (Monday)
    week_start = target_date - timedelta(days=target_date.weekday())

    days = []
    for day_offset in range(7):
        current_date = week_start + timedelta(days=day_offset)

        stmt = (
            select(Rep)
            .where(Rep.scheduled_date == current_date)
            .order_by(Rep.scheduled_time)
        )
        result = await session.execute(stmt)
        reps = result.scalars().all()

        # Eager-load rep_type and goal
        for rep in reps:
            await session.refresh(rep, ["rep_type", "goal"])

        # Group by goal
        goals_dict = {}
        for rep in reps:
            goal_id = rep.goal_id
            if goal_id not in goals_dict:
                goals_dict[goal_id] = {
                    "goal_id": rep.goal_id,
                    "goal_title": rep.goal.title,
                    "reps": [],
                }

            goals_dict[goal_id]["reps"].append(
                {
                    "rep_id": rep.id,
                    "rep_type_name": rep.rep_type.name,
                    "scheduled_time": rep.scheduled_time.isoformat(),
                    "status": rep.status.value,
                    "completed_at": rep.completed_at.isoformat() if rep.completed_at else None,
                    "duration_minutes": rep.duration_minutes,
                }
            )

        day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][current_date.weekday()]
        days.append({
            "date": current_date.isoformat(),
            "day_name": day_name,
            "goals_with_reps": list(goals_dict.values()),
        })

    return {
        "week_start": week_start.isoformat(),
        "week_end": (week_start + timedelta(days=6)).isoformat(),
        "days": days,
    }
