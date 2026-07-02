"""
Goal CRUD endpoints.

Routes:
    POST   /goals          create
    GET    /goals          list
    GET    /goals/{id}     read
    PATCH  /goals/{id}     update
    DELETE /goals/{id}     delete  (be careful — what happens to its tasks?)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.session import get_session
from app.models import Goal, RepType, Rep
from app.models.goal import GoalStatus
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(payload: GoalCreate, session: AsyncSession = Depends(get_session)):
    # Check for duplicate goal name
    stmt = select(Goal).where(Goal.title == payload.title)
    result = await session.execute(stmt)
    existing = result.scalar()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Goal with name '{payload.title}' already exists",
        )

    goal = Goal(**payload.model_dump())
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return goal



@router.get("", response_model=list[GoalRead])
async def list_goals(session: AsyncSession = Depends(get_session)):
    stmt = select(Goal).order_by(Goal.created_at.desc())
    result = await session.execute(stmt)
    goals = result.scalars().all()
    return goals


@router.get("/{goal_id}", response_model=GoalRead)
async def get_goal(goal_id: UUID, session: AsyncSession = Depends(get_session)):
    goal = await session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(
            status_code=404, 
            detail="Goal not found",
        )
    return goal


@router.patch("/{goal_id}", response_model=GoalRead)
async def update_goal(
    goal_id: UUID, 
    payload: GoalUpdate, 
    session: AsyncSession = Depends(get_session),
    ) -> GoalRead:
    goal = await session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    
    await session.commit()
    await session.refresh(goal)
    return goal

    


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: UUID,
    hard: bool = Query(False, description="If true, permanently delete. If false (default), archive."),
    session: AsyncSession = Depends(get_session),
):
    goal = await session.get(Goal, goal_id)

    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    if hard:
        # Hard delete — permanently remove goal, rep types, and reps
        # Delete reps first (FK constraint)
        await session.execute(delete(Rep).where(Rep.goal_id == goal_id))
        # Delete rep types
        await session.execute(delete(RepType).where(RepType.goal_id == goal_id))
        # Delete goal
        await session.delete(goal)
    else:
        # Soft-delete — archive goal, keeping historical data
        goal.status = GoalStatus.archived

    await session.commit()
    
