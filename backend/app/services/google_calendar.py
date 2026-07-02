"""
Google Calendar integration for reps.

One-way sync: tracker → calendar. Calendar is read-only for us.
All methods async-safe via asyncio.to_thread() (Google SDK is synchronous).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


class GoogleCalendarClient:
    """Async-safe wrapper around Google Calendar API v3."""

    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token

    def _build_service(self):
        """Synchronous build of the Calendar service. Called within asyncio.to_thread()."""
        credentials = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/calendar.events"],
        )
        # Refresh to get an access token
        credentials.refresh(Request())
        return build("calendar", "v3", credentials=credentials)

    async def create_event(
        self,
        rep,
        rep_type_name: str,
        goal_title: str,
        tz: ZoneInfo,
    ) -> str:
        """
        Create a calendar event for a rep.

        Args:
            rep: Rep model instance with scheduled_date, scheduled_time, duration_minutes
            rep_type_name: Name of the rep type (for title prefix)
            goal_title: Title of the goal
            tz: Timezone for datetime construction

        Returns:
            Google Calendar event ID (string)
        """

        def _create():
            try:
                service = self._build_service()
                start_dt = datetime.combine(rep.scheduled_date, rep.scheduled_time).replace(tzinfo=tz)
                end_dt = start_dt + timedelta(minutes=rep.duration_minutes)

                event = {
                    "summary": f"[{rep_type_name}] {goal_title}",
                    "description": getattr(rep, "notes", None) or "",
                    "start": {"dateTime": start_dt.isoformat(), "timeZone": str(tz)},
                    "end": {"dateTime": end_dt.isoformat(), "timeZone": str(tz)},
                    "colorId": "8",  # Graphite (gray)
                    "extendedProperties": {
                        "private": {
                            "rep_id": str(rep.id),
                        }
                    },
                }
                result = service.events().insert(calendarId="primary", body=event).execute()
                logger.info(f"Created calendar event {result['id']} for rep {rep.id}")
                return result["id"]
            except Exception as e:
                logger.warning(f"Calendar sync skipped: {e}")
                return None

        return await asyncio.to_thread(_create)

    async def patch_color(self, event_id: str, color_id: int) -> None:
        """
        Update event color.

        Args:
            event_id: Google Calendar event ID
            color_id: Color ID (10=green/completed, 11=red/missed)
        """

        def _patch():
            try:
                service = self._build_service()
                service.events().patch(
                    calendarId="primary",
                    eventId=event_id,
                    body={"colorId": str(color_id)},
                ).execute()
                logger.info(f"Updated calendar event {event_id} to color {color_id}")
            except Exception as e:
                logger.warning(f"Calendar sync skipped: {e}")

        await asyncio.to_thread(_patch)

    async def delete_event(self, event_id: str) -> None:
        """
        Delete a calendar event.

        Args:
            event_id: Google Calendar event ID
        """

        def _delete():
            try:
                service = self._build_service()
                service.events().delete(
                    calendarId="primary",
                    eventId=event_id,
                ).execute()
                logger.info(f"Deleted calendar event {event_id}")
            except Exception as e:
                logger.warning(f"Calendar sync skipped: {e}")

        await asyncio.to_thread(_delete)
