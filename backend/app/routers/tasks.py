"""
Tasks — calendar events tagged to a goal (calendar-first redesign).

Routes:
    GET  /tasks                     tasks for one day (?date=YYYY-MM-DD, default today)
    GET  /tasks/graph               goals and tasks as nodes and links for one day (?date=,
                                    default today) or one Mon–Sun week (?week_start=)
    POST /tasks/sync                pull one day from Google Calendar now (?date=, default today)
    POST /tasks/{id}/complete       check a task off; its event turns green
    POST /tasks/{id}/cancel-reason  say why a removed task was removed

There is no create, update or delete: the calendar is where tasks are made.
"""

from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.session import get_session
from app.models import Task, TaskStatus
from app.schemas.task import TaskCancelReason, TaskGraphRead, TaskRead, TaskSyncRead
from app.services.google_calendar import GoogleCalendarClient
from app.services.summary import week_start_for
from app.services.task_graph import get_task_graph
from app.services.task_sync import sync_tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _today() -> date:
    return datetime.now(tz=settings.tz).date()


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    on: date | None = Query(None, alias="date"),
    session: AsyncSession = Depends(get_session),
):
    day = on or _today()
    tasks = (
        await session.execute(
            select(Task)
            .where(Task.scheduled_date == day)
            .options(selectinload(Task.goal))
            # All-day first (null start_time), then by time.
            .order_by(Task.start_time.asc().nulls_first(), Task.title)
        )
    ).scalars()
    return [_read(t) for t in tasks]


def _read(task: Task) -> TaskRead:
    """goal_title lives on the goal, not the task, so it is filled in by hand."""
    return TaskRead(
        **{f: getattr(task, f) for f in TaskRead.model_fields if f != "goal_title"},
        goal_title=task.goal.title,
    )


@router.get("/graph", response_model=TaskGraphRead)
async def task_graph(
    on: date | None = Query(None, alias="date"),
    week_start: date | None = Query(None, description="Any day in the week; snapped to its Monday"),
    session: AsyncSession = Depends(get_session),
):
    if on is not None and week_start is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ask for a day or a week, not both",
        )
    if week_start is not None:
        # The one definition of a week (Mon–Sun), shared with the rep metrics.
        monday = week_start_for(week_start)
        return await get_task_graph(session, monday, monday + timedelta(days=6))
    day = on or _today()
    return await get_task_graph(session, day, day)


@router.post("/sync", response_model=TaskSyncRead)
async def sync_day(
    on: date | None = Query(None, alias="date"),
    session: AsyncSession = Depends(get_session),
):
    if not settings.google_calendar_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Calendar is not configured",
        )
    day = on or _today()
    client = GoogleCalendarClient(
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_refresh_token,
    )
    try:
        result = await sync_tasks(session, client, day, day, settings.tz)
    except IntegrityError:
        # The 15-minute job and this button inserted the same event at the same
        # moment; the UNIQUE constraint kept one. Nothing is lost.
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A sync was already running. Try again.",
        )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Google Calendar. Nothing was changed.",
        )
    return result


COMPLETED_COLOR_ID = 10  # Basil (green) — same colour a completed rep gets


async def _get_task(session: AsyncSession, task_id: UUID) -> Task:
    task = await session.get(Task, task_id, options=[selectinload(Task.goal)])
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _require_day_not_over(task: Task) -> None:
    """Tasks are answered for until midnight; after that the 00:00 sweep owns them."""
    if task.scheduled_date < _today():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That day is over. Tasks can only be changed until midnight.",
        )


@router.post("/{task_id}/complete", response_model=TaskRead)
async def complete_task(task_id: UUID, session: AsyncSession = Depends(get_session)):
    task = await _get_task(session, task_id)
    if task.status != TaskStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot complete a {task.status.value} task",
        )
    _require_day_not_over(task)

    task.status = TaskStatus.completed
    task.completed_at = datetime.now(tz=settings.tz)
    # The database first, then Google: the check-off is recorded even if the
    # calendar is unreachable, and patch_color never raises.
    await session.commit()

    if settings.google_calendar_enabled:
        client = GoogleCalendarClient(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
        )
        await client.patch_color(task.calendar_event_id, COMPLETED_COLOR_ID)

    return _read(task)


@router.post("/{task_id}/cancel-reason", response_model=TaskRead)
async def give_cancel_reason(
    task_id: UUID,
    payload: TaskCancelReason,
    session: AsyncSession = Depends(get_session),
):
    task = await _get_task(session, task_id)
    if task.status != TaskStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a removed task takes a reason",
        )
    if task.cancel_reason is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This task already has a reason",
        )
    # Decided 2026-09-24: a reason not given by the end of the task's day is
    # dropped — the question goes away rather than following Chris around.
    _require_day_not_over(task)

    task.cancel_reason = payload.reason
    await session.commit()
    return _read(task)
