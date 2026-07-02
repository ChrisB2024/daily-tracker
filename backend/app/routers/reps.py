"""
Rep CRUD + status transitions.

Routes:
    POST   /reps               create (goal_id + rep_type_id required — enforced at DB and schema)
    GET    /reps               list (optional ?date=YYYY-MM-DD filter)
    GET    /reps/{id}          read
    PATCH  /reps/{id}          update
    DELETE /reps/{id}          delete
    POST   /reps/{id}/complete mark completed
    POST   /reps/mark-missed   end-of-day sweep (manual trigger for Slice 1)
"""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.models import Rep, RepStatus, RepType
from app.schemas.rep import RepCreate, RepBulkCreate, RepRead, RepUpdate
from app.services.google_calendar import GoogleCalendarClient

router = APIRouter(prefix="/reps", tags=["reps"])


@router.post("/bulk", response_model=list[RepRead], status_code=status.HTTP_201_CREATED)
async def create_reps_bulk(payload: RepBulkCreate, session: AsyncSession = Depends(get_session)):
    created = []
    for rep_data in payload.reps:
        rep_type = await session.get(RepType, rep_data.rep_type_id)
        if rep_type is None:
            raise HTTPException(status_code=404, detail="RepType not found")
        if rep_type.goal_id != rep_data.goal_id:
            raise HTTPException(
                status_code=400,
                detail="rep_type does not belong to the supplied goal",
            )
        data = rep_data.model_dump()
        data["duration_minutes"] = rep_type.duration_minutes
        rep = Rep(**data)
        session.add(rep)
        created.append(rep)

    await session.commit()

    for rep in created:
        await session.refresh(rep, ["rep_type", "goal"])
        if settings.google_calendar_enabled:
            client = GoogleCalendarClient(
                settings.google_client_id,
                settings.google_client_secret,
                settings.google_refresh_token,
            )
            event_id = await client.create_event(
                rep,
                rep.rep_type.name,
                rep.goal.title,
                settings.tz,
            )
            rep.calendar_event_id = event_id

    await session.commit()
    return created


@router.post("", response_model=RepRead, status_code=status.HTTP_201_CREATED)
async def create_rep(payload: RepCreate, session: AsyncSession = Depends(get_session)):
    rep_type = await session.get(RepType, payload.rep_type_id)
    if rep_type is None:
        raise HTTPException(status_code=404, detail="RepType not found")
    if rep_type.goal_id != payload.goal_id:
        raise HTTPException(
            status_code=400,
            detail="rep_type does not belong to the supplied goal",
        )

    data = payload.model_dump()
    data["duration_minutes"] = rep_type.duration_minutes
    rep = Rep(**data)
    session.add(rep)
    await session.commit()
    await session.refresh(rep, ["rep_type", "goal"])

    if settings.google_calendar_enabled:
        client = GoogleCalendarClient(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
        )
        event_id = await client.create_event(
            rep,
            rep.rep_type.name,
            rep.goal.title,
            settings.tz,
        )
        rep.calendar_event_id = event_id
        await session.commit()

    return rep


@router.get("", response_model=list[RepRead])
async def list_reps(
    scheduled_date: date | None = Query(default=None, alias="date"),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Rep).order_by(Rep.scheduled_time)
    if scheduled_date is not None:
        stmt = stmt.where(Rep.scheduled_date == scheduled_date)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{rep_id}", response_model=RepRead)
async def get_rep(rep_id: UUID, session: AsyncSession = Depends(get_session)):
    rep = await session.get(Rep, rep_id)
    if rep is None:
        raise HTTPException(
            status_code=404, 
            detail="Rep not found",
        )
    return rep


@router.patch("/{rep_id}", response_model=RepRead)
async def update_rep(rep_id: UUID, payload: RepUpdate, session: AsyncSession = Depends(get_session)):
    rep = await session.get(Rep, rep_id)
    if rep is None:
        raise HTTPException(
            status_code=404, 
            detail="Rep not found"
        )
    
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rep, field, value)
    
    await session.commit()
    await session.refresh(rep)
    return rep


@router.delete("/{rep_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rep(rep_id: UUID, session: AsyncSession = Depends(get_session)):
    rep = await session.get(Rep, rep_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Rep not found")

    # Delete from Google Calendar if synced
    if settings.google_calendar_enabled and rep.calendar_event_id:
        client = GoogleCalendarClient(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
        )
        await client.delete_event(rep.calendar_event_id)

    # Delete rep from database
    await session.delete(rep)
    await session.commit()


@router.post("/{rep_id}/complete", response_model=RepRead)
async def complete_rep(rep_id: UUID, session: AsyncSession = Depends(get_session)):
    rep = await session.get(Rep, rep_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Rep not found")
    if rep.status != RepStatus.pending:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot complete a {rep.status.value} rep",
        )
    rep.status = RepStatus.completed
    rep.completed_at = datetime.now(tz=settings.tz)

    if settings.google_calendar_enabled and rep.calendar_event_id:
        client = GoogleCalendarClient(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
        )
        await client.patch_color(rep.calendar_event_id, 10)  # 10 = green

    await session.commit()
    await session.refresh(rep)
    return rep


@router.post("/mark-missed", response_model=None)
async def mark_missed(session: AsyncSession = Depends(get_session)):
    today_date = datetime.now(tz=settings.tz).date()

    # Fetch all pending reps that should be marked missed
    stmt = select(Rep).where(Rep.status == RepStatus.pending, Rep.scheduled_date <= today_date)
    result = await session.execute(stmt)
    reps_to_miss = result.scalars().all()

    # Extract calendar event IDs for patching
    event_ids = [rep.calendar_event_id for rep in reps_to_miss if rep.calendar_event_id]

    # Bulk update status
    update_stmt = (
        update(Rep)
        .where(Rep.status == RepStatus.pending, Rep.scheduled_date <= today_date)
        .values(status=RepStatus.missed)
    )
    update_result = await session.execute(update_stmt)
    await session.commit()

    # Patch calendar colors
    if settings.google_calendar_enabled and event_ids:
        client = GoogleCalendarClient(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
        )
        for event_id in event_ids:
            await client.patch_color(event_id, 11)  # 11 = red

    return {"marked_missed": update_result.rowcount}
