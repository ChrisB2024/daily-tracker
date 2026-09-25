"""
Web push subscriptions (Build Plan 3, Unit 23).

Routes:
    GET    /push/config      whether push is configured, and the VAPID public key
    POST   /push/subscribe   store this device's subscription (idempotent)
    DELETE /push/subscribe   forget this device
    POST   /push/test        send a test notification to every device

The API is unauthenticated (architecture.md S2), so anyone with the URL could
subscribe a device of their own. That exposes nothing new: the same person can
already read every task through GET /tasks.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.models import PushSubscription
from app.schemas.push import PushConfigRead, PushSubscribe, PushTestRead, PushUnsubscribe
from app.services.push import send_to_all

router = APIRouter(prefix="/push", tags=["push"])


def _require_push() -> None:
    if not settings.push_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications are not configured on the server",
        )


@router.get("/config", response_model=PushConfigRead)
async def push_config():
    return PushConfigRead(
        enabled=settings.push_enabled,
        public_key=settings.vapid_public_key if settings.push_enabled else None,
    )


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(payload: PushSubscribe, session: AsyncSession = Depends(get_session)):
    _require_push()
    existing = (
        await session.execute(
            select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            PushSubscription(
                endpoint=payload.endpoint, p256dh=payload.keys.p256dh, auth=payload.keys.auth
            )
        )
    else:
        # Same browser re-subscribing: its keys may have rotated.
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
    await session.commit()


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(payload: PushUnsubscribe, session: AsyncSession = Depends(get_session)):
    await session.execute(
        delete(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    )
    await session.commit()


@router.post("/test", response_model=PushTestRead)
async def send_test(session: AsyncSession = Depends(get_session)):
    _require_push()
    sent = await send_to_all(
        session,
        title="Daily Tracker",
        body="Notifications are working.",
        url="/",
    )
    return PushTestRead(sent=sent)
