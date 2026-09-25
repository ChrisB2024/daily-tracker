from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints

# The browser hands these over from PushManager.subscribe(); the API stores
# them as-is. Lengths are generous bounds, not formats.
Key = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Endpoint = Annotated[str, StringConstraints(pattern=r"^https://", max_length=1000)]


class PushKeys(BaseModel):
    p256dh: Key
    auth: Key


class PushSubscribe(BaseModel):
    endpoint: Endpoint
    keys: PushKeys


class PushUnsubscribe(BaseModel):
    endpoint: Endpoint


class PushConfigRead(BaseModel):
    enabled: bool
    # Public by design: the browser needs it to subscribe. Never the private key.
    public_key: str | None = None


class PushTestRead(BaseModel):
    sent: int
