"""
Google Calendar integration.

Two directions, each with a narrow job (calendar-first redesign, Unit 15):
  - Reps (the old system): tracker → calendar. Events are created, recoloured,
    moved and deleted from here.
  - Tasks: calendar → tracker. Events Chris makes are read with list_events /
    get_event and only ever recoloured — never created, moved or deleted.

All methods async-safe via asyncio.to_thread() (Google SDK is synchronous).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GoogleCalendarClient:
    """Async-safe wrapper around Google Calendar API v3."""

    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        # Built lazily and reused for the life of this instance, so a batch of
        # operations costs one OAuth refresh rather than one per call. Kept
        # per-instance, never module-global: a cached access token must not
        # outlive the request that needed it.
        self._service = None

    def _build_service(self):
        """Synchronous build of the Calendar service. Called within asyncio.to_thread()."""
        if self._service is not None:
            return self._service
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
        self._service = build("calendar", "v3", credentials=credentials)
        return self._service

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
                # Swallowed, per technical invariant 5 — a third-party call must
                # never raise into a request handler. Logged at error with the rep
                # id, because the alternative is a rep that is silently and
                # permanently unsynced with nothing naming it.
                logger.error("Calendar event creation failed for rep %s: %s", rep.id, e)
                return None

        return await asyncio.to_thread(_create)

    async def list_events(self, time_min: datetime, time_max: datetime) -> list[dict] | None:
        """
        Every event on the primary calendar overlapping [time_min, time_max).

        Returns None when Google cannot be reached — never an empty list. The
        difference matters: the sync reads "no events" as "the events were
        deleted", so a network failure dressed as [] would cancel every pending
        task for the day.

        singleEvents=True expands recurring events into their instances, each with
        its own id, so a weekly "[Hitwin] standup" becomes one task per week.
        """

        def _list():
            try:
                service = self._build_service()
                events: list[dict] = []
                page_token = None
                while True:
                    resp = (
                        service.events()
                        .list(
                            calendarId="primary",
                            timeMin=time_min.isoformat(),
                            timeMax=time_max.isoformat(),
                            singleEvents=True,
                            orderBy="startTime",
                            maxResults=250,
                            pageToken=page_token,
                        )
                        .execute()
                    )
                    events.extend(resp.get("items", []))
                    page_token = resp.get("nextPageToken")
                    if not page_token:
                        return events
            except Exception as e:
                logger.error("Calendar list failed for %s to %s: %s", time_min, time_max, e)
                return None

        return await asyncio.to_thread(_list)

    async def get_event(self, event_id: str) -> dict | None:
        """
        One event by id. Used to tell "deleted" apart from "moved elsewhere".

        A deleted event comes back as {"status": "cancelled", ...} — Google either
        still returns it with that status, or answers 404/410, which is folded
        into the same shape. Any other failure returns None: unknown, so the
        caller must change nothing.
        """

        def _get():
            try:
                service = self._build_service()
                return service.events().get(calendarId="primary", eventId=event_id).execute()
            except HttpError as e:
                if e.resp.status in (404, 410):
                    return {"id": event_id, "status": "cancelled"}
                logger.error("Calendar get failed for event %s: %s", event_id, e)
                return None
            except Exception as e:
                logger.error("Calendar get failed for event %s: %s", event_id, e)
                return None

        return await asyncio.to_thread(_get)

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
                logger.error("Calendar colour patch failed for event %s: %s", event_id, e)

        await asyncio.to_thread(_patch)

    async def patch_time(
        self, event_id: str, start_dt: datetime, end_dt: datetime, tz: ZoneInfo
    ) -> None:
        """
        Move an existing event. Without this a rescheduled rep leaves its event
        at the old time forever, and the calendar stops being a mirror.
        """

        def _patch():
            try:
                service = self._build_service()
                service.events().patch(
                    calendarId="primary",
                    eventId=event_id,
                    body={
                        "start": {"dateTime": start_dt.isoformat(), "timeZone": str(tz)},
                        "end": {"dateTime": end_dt.isoformat(), "timeZone": str(tz)},
                    },
                ).execute()
                logger.info("Moved calendar event %s to %s", event_id, start_dt.isoformat())
            except Exception as e:
                logger.error("Calendar time patch failed for event %s: %s", event_id, e)

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
                logger.error("Calendar delete failed for event %s: %s", event_id, e)

        await asyncio.to_thread(_delete)
