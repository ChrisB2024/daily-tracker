"""
Goal model.

Reference (from readme.md):
    Goal
      id: UUID
      title: str
      description: str (nullable)
      target_date: date (nullable)
      status: enum (active | paused | completed | archived)
      created_at: datetime
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GoalStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[GoalStatus] = mapped_column(SQLEnum(GoalStatus), default=GoalStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # cascade does NOT delete children — missed reps must survive goal archival as evidence (non-negotiable)
    rep_types: Mapped[list["RepType"]] = relationship(
        "RepType", back_populates="goal", cascade="save-update, merge"
    )
    reps: Mapped[list["Rep"]] = relationship(
        "Rep", back_populates="goal", cascade="save-update, merge"
    )
