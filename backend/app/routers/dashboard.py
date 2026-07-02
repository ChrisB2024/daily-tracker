"""
Slice 3 dashboard. Renders summary data: daily score, chains, weekly PR, first-rep rate.
Server-side Jinja2 template with summary data from service layer.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.services.summary import (
    get_daily_score,
    get_week_total,
    get_weekly_pr,
    get_first_rep_rate,
    get_chains,
    get_today_reps,
)

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, session: AsyncSession = Depends(get_session)):
    today = datetime.now(tz=settings.tz).date()

    # Fetch all summary data
    daily_score = await get_daily_score(session, today, settings.tz)
    week_total = await get_week_total(session, today, settings.tz)
    weekly_pr = await get_weekly_pr(session, settings.tz)
    first_rep_rate = await get_first_rep_rate(session, today, settings.tz)
    chains = await get_chains(session, settings.tz)
    goals_with_reps = await get_today_reps(session, today)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "today": today,
            "daily_score": daily_score,
            "week_total": week_total,
            "weekly_pr": weekly_pr,
            "first_rep_rate": first_rep_rate,
            "chains": chains,
            "goals_with_reps": goals_with_reps,
        },
    )
