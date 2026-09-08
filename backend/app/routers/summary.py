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
    get_chain_histories,
    get_goal_progressions,
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


class GoalFirstRepRateOut(BaseModel):
    goal_id: UUID
    goal_title: str
    rate: float | None  # None = no first rep scheduled this week, which is not 0%
    days_hit: int
    days_scheduled: int


class DashboardSummary(BaseModel):
    today_date: date
    daily_score: int
    week_total: int
    weekly_pr: int
    first_rep_rates: list[GoalFirstRepRateOut]
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
    - First-rep rate per goal (of days a first rep was scheduled, how many were
      completed before noon)
    - Chains per rep type (independent streaks)
    - Today's reps grouped by goal
    """
    if target_date is None:
        from datetime import datetime
        target_date = datetime.now(tz=settings.tz).date()

    daily_score = await get_daily_score(session, target_date, settings.tz)
    week_total = await get_week_total(session, target_date, settings.tz)
    weekly_pr = await get_weekly_pr(session, settings.tz)
    first_rep_rates = [
        GoalFirstRepRateOut(
            goal_id=r.goal_id,
            goal_title=r.goal_title,
            rate=r.rate,
            days_hit=r.days_hit,
            days_scheduled=r.days_scheduled,
        )
        for r in await get_first_rep_rate(session, target_date, settings.tz)
    ]
    chains = await get_chains(session, settings.tz)
    goals_with_reps = await get_today_reps(session, target_date)
    rhythm_30day = await get_30day_rhythm(session, settings.tz)

    # One query for every goal's progression, and one for every chain's history.
    # Previously this issued a query per goal and a query per rep type on every
    # dashboard load.
    goal_ids = [goal["goal_id"] for goal in goals_with_reps]
    progressions = await get_goal_progressions(session, goal_ids, settings.tz)
    goal_progressions_summary = [
        GoalProgressionInSummary(
            goal_id=goal["goal_id"],
            goal_title=goal["goal_title"],
            progression=[
                ProgressionDataPoint(date=p["date"], cumulative_count=p["cumulative_count"])
                for p in progressions.get(str(goal["goal_id"]), [])
            ],
        )
        for goal in goals_with_reps
    ]

    histories = await get_chain_histories(
        session, [c.rep_type_id for c in chains], settings.tz
    )
    chains_summary = [
        ChainInSummary(
            rep_type_id=chain.rep_type_id,
            rep_type_name=chain.rep_type_name,
            goal_id=chain.goal_id,
            goal_title=chain.goal_title,
            current_chain=chain.current_chain,
            last_completed_date=chain.last_completed_date,
            history=[
                ChainDataPoint(date=h["date"], chain_count=h["chain_count"])
                for h in histories.get(str(chain.rep_type_id), [])
            ],
        )
        for chain in chains
    ]

    return DashboardSummary(
        today_date=target_date,
        daily_score=daily_score,
        week_total=week_total,
        weekly_pr=weekly_pr,
        first_rep_rates=first_rep_rates,
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
