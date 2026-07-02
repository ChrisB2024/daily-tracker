"""
RepType model — a named, binary unit of work attached to a goal.

Reference (from readme.md):
    RepType
      id: UUID
      goal_id: UUID (FK, NOT NULL)
      name: str                    # "Outbound rep"
      criterion: str               # one-line done/not-done definition  ← required, non-negotiable
      duration_minutes: int        # 15-90 typical
      daily_floor: int (nullable)
      weekly_target: int (nullable)
      is_first_rep: bool
      emoji: str (nullable)
      display_order: int
      status: enum (active | archived)
      created_at: datetime

Non-negotiable: criterion is required. The schema enforces "is this a rep or a vibe?"
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RepTypeStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class RepType(Base):
    __tablename__ = "rep_types"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # TODO (Chris): goal_id — NOT NULL FK to goals.id. Same pattern as Rep.goal_id.
    goal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False, index=True)

    # TODO (Chris): name — Text, NOT NULL. Examples: "Outbound rep", "Build rep".
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # TODO (Chris): criterion — Text, NOT NULL.
    # This is the criterion-line discipline gate (non-negotiable). DO NOT make it nullable.
    criterion: Mapped[str] = mapped_column(Text, nullable=False)

    # TODO (Chris): duration_minutes — Integer, NOT NULL. No default (force user to specify
    # 15–90 minute range explicitly — could add a CheckConstraint, but skip for v1).
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # TODO (Chris): daily_floor — Integer, nullable. Minimum reps per day. NULL means
    # this rep type doesn't have a daily floor (only weekly target).
    daily_floor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # TODO (Chris): weekly_target — Integer, nullable. Target reps per week.
    weekly_target: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # TODO (Chris): is_first_rep — Boolean, NOT NULL, default=False.
    # If True, this rep type is the morning non-negotiable for its goal.
    # NOTE: Multiple rep types per goal can have is_first_rep=True (e.g. "Build" and "Outbound" both flagged).
    is_first_rep: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # TODO (Chris): emoji — String(8), nullable. Used in dashboard rendering.
    emoji: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # TODO (Chris): display_order — Integer, NOT NULL, default=0. Controls UI ordering.
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # TODO (Chris): status — RepTypeStatus enum, NOT NULL, default=RepTypeStatus.active.
    status: Mapped[RepTypeStatus] = mapped_column(SQLEnum(RepTypeStatus), nullable=False, default=RepTypeStatus.active)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # TODO (Chris): goal relationship — back_populates="rep_types".
    goal: Mapped["Goal"] = relationship(back_populates="rep_types")

    # TODO (Chris): reps relationship — back_populates="rep_type".
    # Same cascade reasoning as Goal.rep_types: do NOT delete reps when rep_type is archived.
    # Missed reps survive as evidence.
    reps: Mapped[list["Rep"]] = relationship(back_populates="rep_type")
