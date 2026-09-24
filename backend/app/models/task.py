"""
Task model — one Google Calendar event, tagged to a goal, with a binary outcome.

Introduced by the calendar-first redesign (context/specs/14-calendar-first-redesign.md).
The calendar is where work gets planned; a task is the tracker's record of what
happened to it.

    Task
      id: UUID
      goal_id: UUID (FK, NOT NULL)         resolved from the "[Goal] ..." title prefix
      calendar_event_id: str (NOT NULL, UNIQUE)
      title: text                          event title with the prefix stripped
      scheduled_date: date                 in settings.tz
      start_time / end_time: time          null for all-day events
      is_all_day: bool
      duration_minutes: int                the event's length on the calendar
      status: enum (pending | completed | missed | cancelled)
      completed_at: datetime (nullable)
      cancel_reason: text (nullable)       written by Chris after the event was deleted
      created_at / updated_at: datetime

A task is deliberately not a Rep. A rep requires a rep type; a task has none, and
fitting tasks into `reps` would mean rewriting a column on the table that holds
the rep history.

State machine — every arrow is one-way, every end state is terminal:

    pending --checkbox, before midnight--> completed
    pending --00:00 sweep----------------> missed
    pending --event deleted in Google----> cancelled

Nothing read from Google may change a task once it has left `pending`.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TaskStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    missed = "missed"
    cancelled = "cancelled"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    goal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False, index=True
    )

    # The event is the task's identity. UNIQUE is what lets a sync run every 15
    # minutes and upsert: the same event can never become two tasks.
    calendar_event_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)

    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Stored rather than derived from start/end: an all-day event has no times,
    # and a timed event can cross midnight, where end_time < start_time.
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus), nullable=False, default=TaskStatus.pending
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # One line, not a journal. The API is unauthenticated (architecture.md S2),
    # so nothing written here may be something whose disclosure would matter.
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # A pending task is rewritten when its event moves or is renamed.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # One-directional on purpose: Goal is not edited in this unit, and nothing
    # yet needs goal.tasks.
    goal: Mapped["Goal"] = relationship()
