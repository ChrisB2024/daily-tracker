from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GoalRelationCreate(BaseModel):
    # Either order; the router stores it with the smaller id first.
    goal_a_id: UUID
    goal_b_id: UUID


class GoalRelationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    goal_a_id: UUID
    goal_b_id: UUID
