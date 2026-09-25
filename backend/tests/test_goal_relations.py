"""
Goal relations (Unit 25): Chris marks two goals as related; the graph draws a
line between their hubs. Nothing is inferred from dates or titles.
"""

from datetime import date

from sqlalchemy import select

from app.models import GoalRelation, Task, TaskStatus

DAY = date(2026, 9, 24)


async def _goal(client, title):
    return (await client.post("/goals", json={"title": title})).json()["id"]


async def test_relate_list_and_unrelate(client):
    a, b = await _goal(client, "Hitwin"), await _goal(client, "Angle")

    r = await client.post("/goal-relations", json={"goal_a_id": a, "goal_b_id": b})
    assert r.status_code == 201
    rel = r.json()
    assert {rel["goal_a_id"], rel["goal_b_id"]} == {a, b}
    assert rel["goal_a_id"] < rel["goal_b_id"], "stored as an ordered pair"

    assert len((await client.get("/goal-relations")).json()) == 1
    assert (await client.delete(f"/goal-relations/{rel['id']}")).status_code == 204
    assert (await client.get("/goal-relations")).json() == []


async def test_a_pair_is_one_relation_in_either_order(client):
    a, b = await _goal(client, "Hitwin"), await _goal(client, "Angle")
    assert (await client.post("/goal-relations", json={"goal_a_id": a, "goal_b_id": b})).status_code == 201
    again = await client.post("/goal-relations", json={"goal_a_id": b, "goal_b_id": a})
    assert again.status_code == 409


async def test_rejects_self_and_unknown_goals(client):
    a = await _goal(client, "Hitwin")
    assert (await client.post("/goal-relations", json={"goal_a_id": a, "goal_b_id": a})).status_code == 400
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await client.post("/goal-relations", json={"goal_a_id": a, "goal_b_id": missing})).status_code == 404


async def test_graph_draws_only_related_goal_links(client, session):
    from uuid import UUID

    h, a, p = [UUID(await _goal(client, t)) for t in ("Hitwin", "Angle", "Physical")]
    # All three worked the same day — that alone must draw nothing between them.
    session.add_all([
        Task(goal_id=g, calendar_event_id=f"e{i}", title=f"t{i}", scheduled_date=DAY,
             duration_minutes=30, status=TaskStatus.completed)
        for i, g in enumerate((h, a, p))
    ])
    await session.commit()
    await client.post("/goal-relations", json={"goal_a_id": str(h), "goal_b_id": str(a)})

    for params in ({"date": "2026-09-24"}, {"week_start": "2026-09-21"}):
        links = (await client.get("/tasks/graph", params=params)).json()["links"]
        related = [l for l in links if l["kind"] == "related"]
        assert len(related) == 1, params
        assert {related[0]["source"], related[0]["target"]} == {f"goal:{h}", f"goal:{a}"}
        assert all(l["kind"] in ("task", "related") for l in links)


async def test_relation_to_a_goal_not_on_screen_is_not_drawn(client, session):
    from uuid import UUID

    h, a = UUID(await _goal(client, "Hitwin")), UUID(await _goal(client, "Angle"))
    session.add(Task(goal_id=h, calendar_event_id="e1", title="x", scheduled_date=DAY,
                     duration_minutes=30, status=TaskStatus.completed))
    await session.commit()
    await client.post("/goal-relations", json={"goal_a_id": str(h), "goal_b_id": str(a)})

    links = (await client.get("/tasks/graph", params={"date": "2026-09-24"})).json()["links"]
    assert [l["kind"] for l in links] == ["task"], "Angle has no task today, so no line to it"


async def test_hard_deleting_a_goal_removes_its_relations(client, session):
    a, b = await _goal(client, "Oops"), await _goal(client, "Angle")
    await client.post("/goal-relations", json={"goal_a_id": a, "goal_b_id": b})

    assert (await client.delete(f"/goals/{a}", params={"hard": "true"})).status_code == 204
    session.expire_all()
    assert (await session.execute(select(GoalRelation))).scalars().all() == []
