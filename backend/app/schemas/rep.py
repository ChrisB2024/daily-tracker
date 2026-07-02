from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.rep import RepStatus


class RepCreate(BaseModel):
    # TODO (Chris): decide whether `goal_id` is client-supplied (denormalized as in the readme)
    # or derived server-side from rep_type. Keeping it explicit + client-supplied is simpler
    # for now — the create endpoint should also assert rep_type.goal_id == payload.goal_id.
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
