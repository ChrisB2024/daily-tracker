"""
Goal relations — which goals Chris says are related (Unit 25).

Routes:
    GET    /goal-relations        every relation
    POST   /goal-relations        relate two goals (either order; 409 if already related)
    DELETE /goal-relations/{id}   un-relate them

A relation is a statement about goals, not work evidence, so deleting one is
fine and needs no guard.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Goal, GoalRelation
from app.schemas.goal_relation import GoalRelationCreate, GoalRelationRead

router = APIRouter(prefix="/goal-relations", tags=["goal-relations"])


@router.get("", response_model=list[GoalRelationRead])
async def list_relations(session: AsyncSession = Depends(get_session)):
    return (
        (await session.execute(select(GoalRelation).order_by(GoalRelation.created_at)))
        .scalars()
        .all()
    )


@router.post("", response_model=GoalRelationRead, status_code=status.HTTP_201_CREATED)
async def create_relation(payload: GoalRelationCreate, session: AsyncSession = Depends(get_session)):
    if payload.goal_a_id == payload.goal_b_id:
        raise HTTPException(status_code=400, detail="A goal cannot be related to itself")
    for goal_id in (payload.goal_a_id, payload.goal_b_id):
        if await session.get(Goal, goal_id) is None:
            raise HTTPException(status_code=404, detail="Goal not found")

    # UUIDs compare by value, the same order Postgres uses for the CHECK.
    a, b = sorted((payload.goal_a_id, payload.goal_b_id))
    existing = (
        await session.execute(
            select(GoalRelation).where(GoalRelation.goal_a_id == a, GoalRelation.goal_b_id == b)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="These goals are already related")

    relation = GoalRelation(goal_a_id=a, goal_b_id=b)
    session.add(relation)
    await session.commit()
    await session.refresh(relation)
    return relation


@router.delete("/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relation(relation_id: UUID, session: AsyncSession = Depends(get_session)):
    relation = await session.get(GoalRelation, relation_id)
    if relation is None:
        raise HTTPException(status_code=404, detail="Relation not found")
    await session.delete(relation)
    await session.commit()
