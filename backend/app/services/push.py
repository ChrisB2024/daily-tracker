"""
Web push to every subscribed device (Build Plan 3, Unit 23).

Uses the VAPID keys from the environment to sign each message. Like every
integration in services/, it never raises: a failed send is logged and
skipped, and a subscription the push service reports as gone (404 or 410 —
the app was removed or notifications were turned off) is deleted, so it is not
retried forever.
"""

import asyncio
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PushSubscription

logger = logging.getLogger(__name__)

# Seconds the push service keeps an undelivered message (phone off, no
# signal). A reminder that arrives the next morning is worse than none.
TTL_SECONDS = 4 * 60 * 60


def _send_one(subscription: PushSubscription, payload: str) -> str:
    """Synchronous; called through asyncio.to_thread. Returns sent | gone | failed."""
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            ttl=TTL_SECONDS,
        )
        return "sent"
    except WebPushException as e:
        status = e.response.status_code if e.response is not None else None
        if status in (404, 410):
            return "gone"
        # Status only: the exception text can echo request details, and the
        # signed request carries the VAPID token.
        logger.error("Push failed for subscription %s: HTTP %s", subscription.id, status)
        return "failed"
    except Exception as e:  # noqa: BLE001 — a push must never break the caller
        logger.error("Push failed for subscription %s: %s", subscription.id, type(e).__name__)
        return "failed"


async def send_to_all(session: AsyncSession, *, title: str, body: str, url: str = "/") -> int:
    """
    Send one notification to every subscribed device. Returns how many were
    delivered to the push service. `url` is where tapping it opens the app.
    """
    if not settings.push_enabled:
        return 0

    subscriptions = (await session.execute(select(PushSubscription))).scalars().all()
    payload = json.dumps({"title": title, "body": body, "url": url})

    sent = 0
    gone = []
    for sub in subscriptions:
        outcome = await asyncio.to_thread(_send_one, sub, payload)
        if outcome == "sent":
            sent += 1
        elif outcome == "gone":
            gone.append(sub.id)

    if gone:
        await session.execute(delete(PushSubscription).where(PushSubscription.id.in_(gone)))
        await session.commit()
        logger.info("Removed %s expired push subscription(s)", len(gone))

    logger.info("Push '%s' sent to %s of %s device(s)", title, sent, len(subscriptions))
    return sent
