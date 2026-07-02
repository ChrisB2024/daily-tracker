"""
History view — all-time goal progressions.

Routes:
    GET /history — returns all active goals with cumulative progression from creation to today
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.models import Goal, GoalStatus
from app.services.summary import get_goal_progression_alltime

router = APIRouter(prefix="/history", tags=["history"])


class ProgressionDataPoint(BaseModel):
    date: str
    cumulative_count: int


class GoalHistoryItem(BaseModel):
    goal_id: UUID
    goal_title: str
    created_date: date
    progression: list[ProgressionDataPoint]


@router.get("", response_model=list[GoalHistoryItem])
async def get_history(session: AsyncSession = Depends(get_session)):
    """
    Get all-time progression for all active goals.

    Returns one entry per goal with full cumulative progression from creation to today.
    """
    stmt = select(Goal).where(Goal.status == GoalStatus.active).order_by(Goal.created_at.desc())
    result = await session.execute(stmt)
    goals = result.scalars().all()

    history = []
    for goal in goals:
        start_date = goal.created_at.date()
        progression_data = await get_goal_progression_alltime(session, str(goal.id), start_date, settings.tz)
        progression = [
            ProgressionDataPoint(date=p["date"], cumulative_count=p["cumulative_count"])
            for p in progression_data
        ]
        history.append(
            GoalHistoryItem(
                goal_id=goal.id,
                goal_title=goal.title,
                created_date=start_date,
                progression=progression,
            )
        )

    return history
