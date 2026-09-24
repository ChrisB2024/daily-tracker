from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.task import TaskStatus

# No TaskCreate and no TaskUpdate: tasks are created and reshaped only by the
# calendar sync, and their status moves only through dedicated endpoints. The
# one thing the client may write is a removal reason.


class TaskCancelReason(BaseModel):
    # One line, not a journal: the API is unauthenticated (architecture.md S2).
    # Stripped before the length check, so "   " is rejected rather than stored as "".
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


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


class TaskGraphNode(BaseModel):
    id: str  # "goal:<uuid>" or "task:<uuid>" — goal and task ids never collide
    kind: str  # "goal" | "task"
    goal_id: str
    label: str
    # goal nodes
    color_slot: int | None = None  # 1..6 → the --goal-N token; fixed per goal
    task_count: int | None = None
    completed_count: int | None = None
    minutes_completed: int | None = None
    minutes_planned: int | None = None
    # task nodes
    status: TaskStatus | None = None
    duration_minutes: int | None = None
    scheduled_date: date | None = None


class TaskGraphLink(BaseModel):
    source: str
    target: str
    kind: str = "task"  # "task" (task → goal) | "shared_day" (goal ↔ goal)
    weight: int | None = None  # shared_day only: days both goals were worked


class TaskGraphRead(BaseModel):
    start_date: date
    end_date: date
    nodes: list[TaskGraphNode]
    links: list[TaskGraphLink]
