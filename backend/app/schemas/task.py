from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.task import TaskStatus

# No TaskCreate and no TaskUpdate: tasks are created and reshaped only by the
# calendar sync, and their status moves only through dedicated endpoints
# (Unit 16). The client has nothing it may set yet.


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    goal_id: UUID
    # Carried so the daily list can group by goal without a second request.
    goal_title: str
    calendar_event_id: str
    title: str
    scheduled_date: date
    start_time: time | None = None
    end_time: time | None = None
    is_all_day: bool
    duration_minutes: int
    status: TaskStatus
    completed_at: datetime | None = None
    cancel_reason: str | None = None


class TaskSyncRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    start_date: date
    end_date: date
    synced_at: datetime
    created: int
    updated: int
    cancelled: int
    unchanged: int
    untagged: int
    rep_events_skipped: int
    unmatched: list[str]
