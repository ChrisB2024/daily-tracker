"""
Web push plumbing (Build Plan 3, Unit 23). pywebpush's webpush() is replaced,
so no test ever contacts a push service.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import PushSubscription

SUB = {
    "endpoint": "https://web.push.apple.com/abc123",
    "keys": {"p256dh": "BPubKey", "auth": "authsecret"},
}


@pytest.fixture
def push_on(monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "PUBLIC")
    monkeypatch.setattr(settings, "vapid_private_key", "PRIVATE")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:test@example.com")


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


@pytest.fixture
def pushes(monkeypatch):
    """Records every webpush() call; endpoints in `fail` raise with that status."""
    import app.services.push as push_service
    from pywebpush import WebPushException

    calls, fail = [], {}

    def fake_webpush(subscription_info, data, **kw):
        calls.append((subscription_info["endpoint"], data))
        status = fail.get(subscription_info["endpoint"])
        if status:
            raise WebPushException("nope", response=FakeResponse(status))

    monkeypatch.setattr(push_service, "webpush", fake_webpush)
    return calls, fail


async def _endpoints(session):
    session.expire_all()
    return sorted((await session.execute(select(PushSubscription.endpoint))).scalars())


async def test_config_reports_disabled_without_keys(client):
    r = await client.get("/push/config")
    assert r.json() == {"enabled": False, "public_key": None}
    assert (await client.post("/push/subscribe", json=SUB)).status_code == 503
    assert (await client.post("/push/test")).status_code == 503


async def test_config_exposes_only_the_public_key(client, push_on):
    body = (await client.get("/push/config")).json()
    assert body == {"enabled": True, "public_key": "PUBLIC"}
    assert "PRIVATE" not in str(body)


async def test_subscribe_is_idempotent_and_unsubscribe_forgets(client, session, push_on):
    assert (await client.post("/push/subscribe", json=SUB)).status_code == 204
    rotated = {**SUB, "keys": {"p256dh": "NewKey", "auth": "newauth"}}
    assert (await client.post("/push/subscribe", json=rotated)).status_code == 204

    rows = (await session.execute(select(PushSubscription))).scalars().all()
    assert len(rows) == 1 and rows[0].p256dh == "NewKey"

    r = await client.request("DELETE", "/push/subscribe", json={"endpoint": SUB["endpoint"]})
    assert r.status_code == 204
    assert await _endpoints(session) == []


async def test_endpoint_must_be_https(client, push_on):
    bad = {**SUB, "endpoint": "http://evil.example/x"}
    assert (await client.post("/push/subscribe", json=bad)).status_code == 422


async def test_test_push_sends_and_drops_gone_devices(client, session, push_on, pushes):
    calls, fail = pushes
    for n in range(3):
        await client.post("/push/subscribe", json={**SUB, "endpoint": f"https://push.example/{n}"})
    fail["https://push.example/1"] = 410  # app removed from the phone
    fail["https://push.example/2"] = 500  # push service hiccup: keep it

    r = await client.post("/push/test")
    assert r.status_code == 200 and r.json() == {"sent": 1}
    assert len(calls) == 3
    assert '"Notifications are working."' in calls[0][1]
    assert await _endpoints(session) == ["https://push.example/0", "https://push.example/2"]


def test_generated_vapid_keys_are_a_matching_pair():
    """The script's two keys must belong together, or every push fails with 403."""
    import base64

    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid

    script = Path(__file__).parent.parent / "scripts" / "generate_vapid_keys.py"
    out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True)
    values = dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line)

    derived = Vapid.from_string(values["VAPID_PRIVATE_KEY"]).public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    assert base64.urlsafe_b64encode(derived).rstrip(b"=").decode() == values["VAPID_PUBLIC_KEY"]
