"""
Weekly debrief endpoint.

GET /debrief — generates weekly summary with audio.
"""

from datetime import date
from pydantic import BaseModel

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.services.debrief import get_debrief

router = APIRouter(prefix="/debrief", tags=["debrief"])


class DebriefResponse(BaseModel):
    week_start: str
    week_end: str
    summary: str
    audio_base64: str
    stats: dict


@router.get("", response_model=DebriefResponse)
async def generate_debrief(
    target_date: date | None = Query(default=None, alias="date"),
    session: AsyncSession = Depends(get_session),
) -> DebriefResponse:
    """
    Generate weekly debrief summary with audio.

    If debrief is not configured (missing Claude API key or ElevenLabs key),
    returns empty summary and audio.
    """
    if target_date is None:
        from datetime import datetime

        target_date = datetime.now(tz=settings.tz).date()

    if not settings.debrief_enabled:
        return DebriefResponse(
            week_start="",
            week_end="",
            summary="Debrief feature not configured. Add CLAUDE_API_KEY and ELEVENLABS_API_KEY to .env",
            audio_base64="",
            stats={"completed": 0, "missed": 0, "total": 0, "completion_rate": 0},
        )

    result = await get_debrief(session, target_date, settings.tz)
    return DebriefResponse(**result)
