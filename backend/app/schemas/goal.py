"""
Pydantic schemas separate "what we accept over the wire" from "how data is stored."

Three flavours per resource is a common pattern:
  - GoalCreate: fields the client sends to create. No id, no created_at — server owns those.
  - GoalUpdate: fields the client can patch. All optional.
  - GoalRead:   what we send back. Includes id, created_at.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.goal import GoalStatus


class GoalCreate(BaseModel):
    title: str
    description: str | None = None
    target_date: date | None = None


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    target_date: date | None = None
    status: GoalStatus | None = None


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None
    target_date: date | None = None
    status: GoalStatus
    created_at: datetime
