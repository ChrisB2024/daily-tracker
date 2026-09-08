from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.rep import RepStatus


class RepCreate(BaseModel):
    # Client-supplied and denormalised, as in readme.md's data model. Both create
    # endpoints assert rep_type.goal_id == payload.goal_id before inserting, so a
    # mismatch is a 400 rather than a rep filed under the wrong goal.
    goal_id: UUID
    rep_type_id: UUID
    scheduled_date: date
    scheduled_time: time
    duration_minutes: int = 60
    notes: str | None = None


class RepUpdate(BaseModel):
    scheduled_date: date | None = None
    scheduled_time: time | None = None
    duration_minutes: int | None = None
    notes: str | None = None
    # status intentionally omitted — transitions only via /complete and /mark-missed.


class RepBulkCreate(BaseModel):
    reps: list[RepCreate]


class RepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    goal_id: UUID
    rep_type_id: UUID
    scheduled_date: date
    scheduled_time: time
    duration_minutes: int
    status: RepStatus
    notes: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    calendar_event_id: str | None = None
