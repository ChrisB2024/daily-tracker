"""
Rep status transitions and the deletion guard.

These are the paths smoke.py cannot cover, because exercising them writes.
"""

from datetime import date, datetime, timedelta

from app.config import settings
from app.models import RepStatus


async def test_complete_marks_completed_and_stamps_time(client, factory):
    g = await factory.goal()
    rt = await factory.rep_type(g)
    rep = await factory.rep(rt, on=date.today())

    r = await client.post(f"/reps/{rep.id}/complete")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None


async def test_completing_twice_is_rejected(client, factory):
    g = await factory.goal()
    rt = await factory.rep_type(g)
    rep = await factory.rep(rt, on=date.today())

    assert (await client.post(f"/reps/{rep.id}/complete")).status_code == 200
    again = await client.post(f"/reps/{rep.id}/complete")
    assert again.status_code == 409, "completed is terminal"


async def test_missed_cannot_be_completed(client, factory, session):
    g = await factory.goal()
    rt = await factory.rep_type(g)
    rep = await factory.rep(rt, on=date.today(), status=RepStatus.missed)

    r = await client.post(f"/reps/{rep.id}/complete")
    assert r.status_code == 409, "missed is terminal — there is no un-miss"


async def test_pending_rep_can_be_deleted(client, factory):
    g = await factory.goal()
    rt = await factory.rep_type(g)
    rep = await factory.rep(rt, on=date.today())

    assert (await client.delete(f"/reps/{rep.id}")).status_code == 204
    assert (await client.get(f"/reps/{rep.id}")).status_code == 404


async def test_completed_and_missed_reps_cannot_be_deleted(client, factory):
    """
    Product invariant 3: missed reps stay visible. Erasing one erases the
    evidence the system exists to collect.
    """
    g = await factory.goal()
    rt = await factory.rep_type(g)
    done = await factory.rep(rt, on=date.today(), status=RepStatus.completed)
    missed = await factory.rep(rt, on=date.today(), status=RepStatus.missed)

    for rep in (done, missed):
        assert (await client.delete(f"/reps/{rep.id}")).status_code == 409
        assert (await client.get(f"/reps/{rep.id}")).status_code == 200, "still there"


async def test_rep_must_belong_to_the_goal_it_claims(client, factory):
    """No orphan reps, no reps filed under the wrong goal."""
    g1 = await factory.goal("Goal one")
    g2 = await factory.goal("Goal two")
    rt = await factory.rep_type(g1)

    r = await client.post(
        "/reps",
        json={
            "goal_id": str(g2.id),
            "rep_type_id": str(rt.id),
            "scheduled_date": str(date.today()),
            "scheduled_time": "09:00:00",
        },
    )
    assert r.status_code == 400


async def test_duration_comes_from_the_rep_type_not_the_client(client, factory):
    g = await factory.goal()
    rt = await factory.rep_type(g, duration_minutes=45)

    r = await client.post(
        "/reps",
        json={
            "goal_id": str(g.id),
            "rep_type_id": str(rt.id),
            "scheduled_date": str(date.today()),
            "scheduled_time": "09:00:00",
            "duration_minutes": 999,
        },
    )
    assert r.status_code == 201
    assert r.json()["duration_minutes"] == 45, "server owns duration"
