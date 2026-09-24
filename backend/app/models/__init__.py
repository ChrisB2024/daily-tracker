# Re-export models so Alembic + the rest of the app can `from app.models import Goal, ...`.
# Import order matters for relationship resolution: Goal first (referenced by both),
# then RepType (referenced by Rep), then Rep. Task references only Goal.
from app.models.goal import Goal, GoalStatus
from app.models.rep_type import RepType, RepTypeStatus
from app.models.rep import Rep, RepStatus
from app.models.task import Task, TaskStatus
from app.models.weekly_summary import WeeklySummary

__all__ = [
    "Goal",
    "GoalStatus",
    "RepType",
    "RepTypeStatus",
    "Rep",
    "RepStatus",
    "Task",
    "TaskStatus",
    "WeeklySummary",
]
