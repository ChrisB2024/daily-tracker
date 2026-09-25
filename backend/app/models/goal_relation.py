"""
GoalRelation — two goals Chris has marked as related (Unit 25).

    GoalRelation
      id: UUID
      goal_a_id: UUID (FK goals, NOT NULL)
      goal_b_id: UUID (FK goals, NOT NULL)
      created_at: datetime

A relation has no direction. It is stored once, with the smaller id in
goal_a_id, so (Hitwin, Angle) and (Angle, Hitwin) are the same row — the
UNIQUE constraint and the CHECK below make that true in the database, not just
in the router.

It is Chris's own statement, never inferred: the graph draws a line between two
goal hubs only when a row here says so.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GoalRelation(Base):
    __tablename__ = "goal_relations"
    __table_args__ = (
        UniqueConstraint("goal_a_id", "goal_b_id", name="uq_goal_relations_pair"),
        # Ordered pair, and never a goal related to itself.
        CheckConstraint("goal_a_id < goal_b_id", name="ck_goal_relations_ordered"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    goal_a_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False, index=True
    )
    goal_b_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
