"""
The points-and-lines graph of tasks and goals (calendar-first redesign, Units 18–19).

Returns nodes and links in the shape 3d-force-graph draws directly, so the
frontend only renders:

    goal node   one per goal that has a task in the range; its size is the
                minutes of *completed* tasks ("worked more" = time spent)
    task node   one per task, sized by its duration
    link        task → its goal. Tasks sharing a goal are joined through it,
                which is what makes each goal read as a cluster.

Cancelled tasks are left out: the event was deleted, so it was never work.
Missed tasks are kept — a miss is evidence and is never hidden.

Metrics are computed here, at read time, and never stored.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Goal, Task, TaskStatus

# How many --goal-N colour tokens the frontend defines.
GOAL_COLOR_COUNT = 6


async def get_task_graph(session: AsyncSession, start: date, end: date) -> dict:
    """Graph of every non-cancelled task scheduled start..end inclusive."""
    tasks = (
        await session.execute(
            select(Task)
            .where(
                Task.scheduled_date >= start,
                Task.scheduled_date <= end,
                Task.status != TaskStatus.cancelled,
            )
            .options(selectinload(Task.goal))
            .order_by(Task.scheduled_date, Task.start_time.asc().nulls_first())
        )
    ).scalars().all()

    # A goal keeps one colour in every view: its slot is its position among all
    # goals by creation order, not its rank in this particular day or week.
    goal_order = (
        await session.execute(select(Goal.id).order_by(Goal.created_at, Goal.id))
    ).scalars().all()
    color_slot = {gid: i % GOAL_COLOR_COUNT + 1 for i, gid in enumerate(goal_order)}

    goals: dict = {}
    task_nodes = []
    links = []

    for t in tasks:
        g = goals.setdefault(
            t.goal_id,
            {
                "id": f"goal:{t.goal_id}",
                "kind": "goal",
                "goal_id": str(t.goal_id),
                "label": t.goal.title,
                "color_slot": color_slot[t.goal_id],
                "task_count": 0,
                "completed_count": 0,
                "minutes_completed": 0,
                "minutes_planned": 0,
            },
        )
        g["task_count"] += 1
        g["minutes_planned"] += t.duration_minutes
        if t.status == TaskStatus.completed:
            g["completed_count"] += 1
            g["minutes_completed"] += t.duration_minutes

        task_nodes.append(
            {
                "id": f"task:{t.id}",
                "kind": "task",
                "goal_id": str(t.goal_id),
                "label": t.title,
                "status": t.status.value,
                "duration_minutes": t.duration_minutes,
                "scheduled_date": t.scheduled_date.isoformat(),
            }
        )
        links.append({"source": f"task:{t.id}", "target": f"goal:{t.goal_id}"})

    # Most time spent first, so the frontend can colour goals in a stable order
    # and Unit 19 can rank them without re-sorting.
    goal_nodes = sorted(
        goals.values(), key=lambda g: (-g["minutes_completed"], g["label"].lower())
    )

    return {
        "start_date": start,
        "end_date": end,
        "nodes": goal_nodes + task_nodes,
        "links": links,
    }
