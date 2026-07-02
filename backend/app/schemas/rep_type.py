from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.rep_type import RepTypeStatus


class RepTypeCreate(BaseModel):
    name: str
    criterion: str = Field(min_length=1)
    duration_minutes: int
    daily_floor: int | None = None
    weekly_target: int | None = None
    is_first_rep: bool = False
    emoji: str | None = None
    display_order: int = 0


class RepTypeUpdate(BaseModel):
    name: str | None = None
    criterion: str | None = Field(default=None, min_length=1)
    duration_minutes: int | None = None
    daily_floor: int | None = None
    weekly_target: int | None = None
    is_first_rep: bool | None = None
    emoji: str | None = None
    display_order: int | None = None
    status: RepTypeStatus | None = None


class RepTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    goal_id: UUID
    name: str
    criterion: str
    duration_minutes: int
    daily_floor: int | None = None
    weekly_target: int | None = None
    is_first_rep: bool
    emoji: str | None = None
    display_order: int
    status: RepTypeStatus
    created_at: datetime
