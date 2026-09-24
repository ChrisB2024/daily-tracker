"""
Tasks — calendar events tagged to a goal (calendar-first redesign).

Routes:
    GET  /tasks        tasks for one day (?date=YYYY-MM-DD, default today)
    POST /tasks/sync   pull one day from Google Calendar now (?date=, default today)

There is no create, update or delete: the calendar is where tasks are made.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.session import get_session
from app.models import Task
from app.schemas.task import TaskRead, TaskSyncRead
from app.services.google_calendar import GoogleCalendarClient
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
