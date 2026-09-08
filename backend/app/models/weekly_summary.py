"""
WeeklySummary model — one persisted snapshot per week.

Reference (readme.md), with one deliberate departure decided 2026-09-07:
**the generated prose is not stored.** Security invariant S2 permits an
unauthenticated API precisely because the database holds only rep metadata —
counts and timestamps, dull and reconstructible. A week-by-week narrative of
what Chris works on and avoids is a different class of data, and persisting it
would have meant widening S2. The numbers are stored; the prose is regenerated
on demand from them.

For the same reason there is no `audio_url`: `architecture.md` forbids blobs in
Postgres and there is no object store, so audio is regenerated too.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeeklySummary(Base):
    __tablename__ = "weekly_summaries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # One row per week. Regenerating a week updates it rather than appending, so
    # opening the debrief view twice does not accumulate duplicates.
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)

    # Per-rep-type stats: chains with deltas, week total, PR comparison,
    # first-rep rates. JSONB rather than JSON — this is a Postgres-only app.
    rep_data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Behavioural patterns: most completed, most avoided, chains that broke.
    patterns: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Set when the email actually sends, which distinguishes "generated" from
    # "delivered". Null for a summary computed by opening the debrief view.
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
