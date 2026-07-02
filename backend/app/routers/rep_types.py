"""
RepType CRUD. Nested under goals where it makes sense.

Routes:
    POST   /goals/{goal_id}/rep-types  create
    GET    /goals/{goal_id}/rep-types  list rep types for a goal
    GET    /rep-types/{id}             read
    PATCH  /rep-types/{id}             update
    DELETE /rep-types/{id}             delete  (soft — status=archived, reps preserved)

The mixed prefix (some routes nested under /goals, some flat under /rep-types) keeps URLs
intuitive: you create+list under the parent, but read/update/delete by RepType id directly.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Goal, RepType, RepTypeStatus
from app.schemas.rep_type import RepTypeCreate, RepTypeRead, RepTypeUpdate

router = APIRouter(tags=["rep-types"])


@router.post(
    "/goals/{goal_id}/rep-types",
    response_model=RepTypeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_rep_type(
    goal_id: UUID,
    payload: RepTypeCreate,
    session: AsyncSession = Depends(get_session),
):
    goal = await session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    rep_type = RepType(**payload.model_dump(), goal_id=goal_id)
    session.add(rep_type)
    await session.commit()
    await session.refresh(rep_type)
    return rep_type


@router.get("/goals/{goal_id}/rep-types", response_model=list[RepTypeRead])
async def list_rep_types_for_goal(
    goal_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(RepType)
        .where(RepType.goal_id == goal_id)
        .order_by(RepType.display_order, RepType.created_at)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/rep-types/{rep_type_id}", response_model=RepTypeRead)
async def get_rep_type(rep_type_id: UUID, session: AsyncSession = Depends(get_session)):
    rep_type = await session.get(RepType, rep_type_id)
    if rep_type is None:
        raise HTTPException(status_code=404, detail="RepType not found")
    return rep_type


@router.patch("/rep-types/{rep_type_id}", response_model=RepTypeRead)
async def update_rep_type(
    rep_type_id: UUID,
    payload: RepTypeUpdate,
    session: AsyncSession = Depends(get_session),
):
    rep_type = await session.get(RepType, rep_type_id)
    if rep_type is None:
        raise HTTPException(status_code=404, detail="RepType not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rep_type, field, value)
    await session.commit()
    await session.refresh(rep_type)
    return rep_type


@router.delete("/rep-types/{rep_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rep_type(rep_type_id: UUID, session: AsyncSession = Depends(get_session)):
    rep_type = await session.get(RepType, rep_type_id)
    if rep_type is None:
        raise HTTPException(status_code=404, detail="RepType not found")
    # Soft-delete keeps historical/missed reps intact while hiding the rep_type from active views.
    rep_type.status = RepTypeStatus.archived
    await session.commit()
