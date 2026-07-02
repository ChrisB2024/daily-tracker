"""
Rep model — a scheduled instance of a RepType.

Reference (from readme.md):
    Rep
      id: UUID
      rep_type_id: UUID (FK, NOT NULL)
      goal_id: UUID (FK, NOT NULL — denormalized for fast queries)
      scheduled_date: date
      scheduled_time: time
      duration_minutes: int        (copied from rep_type at creation)
      calendar_event_id: str (nullable)
      status: enum (pending | completed | missed)
      completed_at: datetime (nullable)
      notes: text (nullable)       (for who+what logging on outbound reps, etc.)
      created_at: datetime

NON-NEGOTIABLE: both rep_type_id and goal_id are NOT NULL. No orphan reps, no untyped reps.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import (
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


class RepStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    missed = "missed"


class Rep(Base):
    __tablename__ = "reps"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    rep_type_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rep_types.id"), nullable=False, index=True
    )

    goal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False, index=True
    )


    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    calendar_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[RepStatus] = mapped_column(SQLEnum(RepStatus), default=RepStatus.pending)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    goal: Mapped["Goal"] = relationship(back_populates="reps")

    rep_type: Mapped["RepType"] = relationship(back_populates="reps")
