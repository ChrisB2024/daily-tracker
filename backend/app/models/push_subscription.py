"""
PushSubscription — one browser (Chris's installed iPhone app) that receives web
push notifications. Build Plan 3, Unit 23.

    PushSubscription
      id: UUID
      endpoint: text (UNIQUE)   the push service URL for this browser
      p256dh: text              browser public key, used to encrypt the payload
      auth: text                browser auth secret, used to encrypt the payload
      created_at: datetime

Why this may live in the unauthenticated database (architecture.md S2): a
subscription only *addresses* the phone. Sending to it needs the VAPID private
key, which lives only in the environment, so a leaked row cannot be used to
push anything.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    # Subscribing twice from the same browser returns the same endpoint; UNIQUE
    # turns that into an update rather than a duplicate notification.
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
