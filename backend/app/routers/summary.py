"""
Dashboard summary endpoint.

GET /summary — returns daily score, chains, today's reps, weekly PR, first-rep rate.
"""

from datetime import date
from pydantic import BaseModel
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.services.summary import (
    get_daily_score,
    get_week_total,
    get_weekly_pr,
    get_first_rep_rate,
    get_chains,
    get_today_reps,
    get_30day_rhythm,
    get_chain_history,
    get_goal_progression,
    get_rep_type_analytics,
    get_week_reps,
)

router = APIRouter(prefix="/summary", tags=["summary"])


class RepInSummary(BaseModel):
    rep_id: UUID
    rep_type_name: str
    scheduled_time: str
    status: str
    duration_minutes: int
    completed_at: str | None = None

    class Config:
        from_attributes = True


class GoalRepsInSummary(BaseModel):
    goal_id: UUID
    goal_title: str
    reps: list[RepInSummary]


class ChainDataPoint(BaseModel):
    date: str
    chain_count: int


class ChainInSummary(BaseModel):
    rep_type_id: UUID
    rep_type_name: str
    goal_id: UUID
    goal_title: str
    current_chain: int
    last_completed_date: date | None
    history: list[ChainDataPoint]


class ProgressionDataPoint(BaseModel):
    date: str
    cumulative_count: int


class GoalProgressionInSummary(BaseModel):
    goal_id: UUID
    goal_title: str
    progression: list[ProgressionDataPoint]


class DashboardSummary(BaseModel):
    today_date: date
    daily_score: int
    week_total: int
    weekly_pr: int
    first_rep_rate: float
    chains: list[ChainInSummary]
    goals_with_reps: list[GoalRepsInSummary]
    rhythm_30day: dict[str, int]  # date ISO string -> completion count
    goal_progressions: list[GoalProgressionInSummary]


class RepTypeAnalytic(BaseModel):
    rep_type_id: UUID
    rep_type_name: str
    goal_id: UUID
    goal_title: str
    total_reps: int
    completed_count: int
    missed_count: int
    pending_count: int
    completion_pct: int


@router.get("", response_model=DashboardSummary)
async def get_summary(
    target_date: date | None = Query(default=None, alias="date"),
    session: AsyncSession = Depends(get_session),
) -> DashboardSummary:
    """
    Get dashboard summary for a target date (default: today).

    Includes:
    - Daily score (completed reps today)
    - Week total (completed reps this week)
    - Weekly PR (all-time best week)
    - First-rep rate (% of days this week where all first-reps were done before noon)
    - Chains per rep type (independent streaks)
    - Today's reps grouped by goal
    """
    if target_date is None:
        from datetime import datetime
        target_date = datetime.now(tz=settings.tz).date()

    daily_score = await get_daily_score(session, target_date, settings.tz)
    week_total = await get_week_total(session, target_date, settings.tz)
    weekly_pr = await get_weekly_pr(session, settings.tz)
    first_rep_rate = await get_first_rep_rate(session, target_date, settings.tz)
    chains = await get_chains(session, settings.tz)
    goals_with_reps = await get_today_reps(session, target_date)
    rhythm_30day = await get_30day_rhythm(session, settings.tz)

    # Get goal progressions for all goals
    goal_ids = {goal["goal_id"] for goal in goals_with_reps}
    goal_progressions_summary = []
    for goal_id_str in goal_ids:
        # Find the goal title from goals_with_reps
        goal_title = next(g["goal_title"] for g in goals_with_reps if g["goal_id"] == goal_id_str)
        progression_data = await get_goal_progression(session, goal_id_str, settings.tz)
        progression = [
            ProgressionDataPoint(date=p["date"], cumulative_count=p["cumulative_count"])
            for p in progression_data
        ]
        goal_progressions_summary.append(
            GoalProgressionInSummary(
                goal_id=goal_id_str,
                goal_title=goal_title,
                progression=progression,
            )
        )

    chains_summary = []
    for chain in chains:
        history_data = await get_chain_history(session, chain.rep_type_id, settings.tz)
        history = [ChainDataPoint(date=h["date"], chain_count=h["chain_count"]) for h in history_data]
        chains_summary.append(
            ChainInSummary(
                rep_type_id=chain.rep_type_id,
                rep_type_name=chain.rep_type_name,
                goal_id=chain.goal_id,
                goal_title=chain.goal_title,
                current_chain=chain.current_chain,
                last_completed_date=chain.last_completed_date,
                history=history,
            )
        )

    return DashboardSummary(
        today_date=target_date,
        daily_score=daily_score,
        week_total=week_total,
        weekly_pr=weekly_pr,
        first_rep_rate=first_rep_rate,
        chains=chains_summary,
        goals_with_reps=goals_with_reps,
        rhythm_30day=rhythm_30day,
        goal_progressions=goal_progressions_summary,
    )


@router.get("/analytics", response_model=list[RepTypeAnalytic])
async def get_analytics(session: AsyncSession = Depends(get_session)) -> list[RepTypeAnalytic]:
    """
    Get completion analytics for all rep types.

    Returns completion %, volume, and breakdown per rep type, sorted by completion % descending.
    """
    analytics = await get_rep_type_analytics(session)
    return [RepTypeAnalytic(**a) for a in analytics]


@router.get("/week")
async def get_week(
    target_date: date | None = Query(default=None, alias="date"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get all reps for the week containing target_date, grouped by day (Mon-Sun).

    Returns week_start, week_end, and list of days with reps grouped by goal.
    """
    if target_date is None:
        from datetime import datetime
        target_date = datetime.now(tz=settings.tz).date()

    return await get_week_reps(session, target_date, settings.tz)
