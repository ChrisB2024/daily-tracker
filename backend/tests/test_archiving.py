"""
Archiving has to actually retire something. It was write-only: the status
changed and nothing read it back, so an archived rep type stayed visible and
schedulable.
"""

from app.models import RepTypeStatus


async def test_archived_rep_type_disappears_from_the_default_listing(client, factory):
    g = await factory.goal()
    rt = await factory.rep_type(g, name="Retired")
    await factory.rep_type(g, name="Active")

    assert (await client.delete(f"/rep-types/{rt.id}")).status_code == 204

    default = (await client.get(f"/goals/{g.id}/rep-types")).json()
    assert [r["name"] for r in default] == ["Active"]

    with_archived = (
        await client.get(f"/goals/{g.id}/rep-types?include_archived=true")
    ).json()
    assert {r["name"] for r in with_archived} == {"Retired", "Active"}


async def test_archiving_a_rep_type_preserves_its_reps(client, factory, session):
    from datetime import date

    g = await factory.goal()
    rt = await factory.rep_type(g)
    rep = await factory.rep(rt, on=date.today())

    await client.delete(f"/rep-types/{rt.id}")

    assert (await client.get(f"/reps/{rep.id}")).status_code == 200, "evidence survives"


async def test_archived_rep_types_are_excluded_from_chains(session, factory):
    from datetime import date

    from app.config import settings
    from app.models import RepStatus
    from app.services.summary import get_chains

    g = await factory.goal()
    live = await factory.rep_type(g, name="Live")
    gone = await factory.rep_type(g, name="Gone", status=RepTypeStatus.archived)
    await factory.rep(live, on=date.today(), status=RepStatus.completed)
    await factory.rep(gone, on=date.today(), status=RepStatus.completed)

    chains = await get_chains(session, settings.tz)
    assert [c.rep_type_name for c in chains] == ["Live"]


async def test_goal_archive_is_soft_and_keeps_children(client, factory):
    from datetime import date

    g = await factory.goal()
    rt = await factory.rep_type(g)
    rep = await factory.rep(rt, on=date.today())

    assert (await client.delete(f"/goals/{g.id}")).status_code == 204
    assert (await client.get(f"/goals/{g.id}")).json()["status"] == "archived"
    assert (await client.get(f"/reps/{rep.id}")).status_code == 200
