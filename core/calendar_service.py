"""Google Calendar service layer."""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from googleapiclient.errors import HttpError
from googleapiclient.discovery import Resource, build
from httplib2 import ServerNotFoundError

from core.auth import MissingCredentialsError, SCOPES, load_google_credentials
from google.oauth2.credentials import Credentials
from utils.config import load_event_cache, save_event_cache

LOCAL_TIMEZONE = ZoneInfo("America/Bogota")
logger = logging.getLogger("zyna-calendar")


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """Normalized event data consumed by the UI layer."""

    event_id: str
    title: str
    start_at: datetime
    is_all_day: bool
    html_link: str


@dataclass(frozen=True, slots=True)
class CalendarSyncResult:
    """Event payload returned to the UI after a sync attempt."""

    events: list[CalendarEvent]
    status_message: str
    is_from_cache: bool = False


class CalendarClient:
    """Thin wrapper around the Google Calendar API."""

    def __init__(self, credentials: Credentials | None = None) -> None:
        """Initialize the calendar client without creating network clients."""

        self._service: Resource | None = None
        self._credentials = credentials

    def list_upcoming_events(
        self,
        calendar_id: str = "primary",
        max_results: int = 10,
    ) -> CalendarSyncResult:
        """Return the next events for a calendar ordered by start time.

        Args:
            calendar_id: Calendar identifier accepted by Google Calendar.
            max_results: Maximum number of events returned by the API.

        Returns:
            A normalized sync result for the UI layer.
        """

        normalized_max_results = max(1, min(5, int(max_results)))
        now = datetime.now(timezone.utc).isoformat()
        try:
            response = (
                self._get_service()
                .events()
                .list(
                    calendarId=calendar_id,
                    timeMin=now,
                    maxResults=normalized_max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except MissingCredentialsError:
            raise
        except Exception as error:
            logger.exception("Calendar sync failed")
            return self._build_fallback_result(error)

        events = response.get("items", [])
        parsed_events = [self._deserialize_event(item) for item in events]
        save_event_cache([self._serialize_event(event) for event in parsed_events])
        return CalendarSyncResult(
            events=parsed_events,
            status_message="Eventos sincronizados.",
            is_from_cache=False,
        )

    def _get_service(self) -> Resource:
        """Create the Google Calendar service on first use."""

        if self._service is None:
            credentials = self._credentials or load_google_credentials(SCOPES)
            self._service = build(
                "calendar",
                "v3",
                credentials=credentials,
                cache_discovery=False,
            )

        return self._service

    def _deserialize_event(self, item: dict[str, Any]) -> CalendarEvent:
        """Convert a raw Google Calendar event into a UI-friendly object."""

        start_at, is_all_day = self._parse_event_start(item.get("start", {}))

        return CalendarEvent(
            event_id=item.get("id", ""),
            title=item.get("summary", "Sin titulo"),
            start_at=start_at,
            is_all_day=is_all_day,
            html_link=item.get("htmlLink", ""),
        )

    def _parse_event_start(
        self,
        start_payload: dict[str, Any],
    ) -> tuple[datetime, bool]:
        """Convert a Google Calendar start payload to America/Bogota."""

        raw_datetime = start_payload.get("dateTime")
        if raw_datetime:
            normalized_value = raw_datetime.replace("Z", "+00:00")
            parsed_datetime = datetime.fromisoformat(normalized_value)

            if parsed_datetime.tzinfo is None:
                parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)

            return parsed_datetime.astimezone(LOCAL_TIMEZONE), False

        raw_date = start_payload.get("date")
        if raw_date:
            parsed_date = date.fromisoformat(raw_date)
            return datetime.combine(
                parsed_date,
                time.min,
                tzinfo=LOCAL_TIMEZONE,
            ), True

        return datetime.now(LOCAL_TIMEZONE), False

    def _serialize_event(self, event: CalendarEvent) -> dict[str, Any]:
        """Serialize an event for local cache persistence."""

        return {
            "event_id": event.event_id,
            "title": event.title,
            "start_at": event.start_at.isoformat(),
            "is_all_day": event.is_all_day,
            "html_link": event.html_link,
        }

    def _deserialize_cached_event(self, item: dict[str, Any]) -> CalendarEvent | None:
        """Restore a cached event payload from disk."""

        try:
            parsed_datetime = datetime.fromisoformat(str(item["start_at"]))
        except (KeyError, TypeError, ValueError):
            return None

        if parsed_datetime.tzinfo is None:
            parsed_datetime = parsed_datetime.replace(tzinfo=LOCAL_TIMEZONE)

        return CalendarEvent(
            event_id=str(item.get("event_id", "")),
            title=str(item.get("title", "Sin titulo")),
            start_at=parsed_datetime.astimezone(LOCAL_TIMEZONE),
            is_all_day=bool(item.get("is_all_day", False)),
            html_link=str(item.get("html_link", "")),
        )

    def _load_cached_events(self) -> list[CalendarEvent]:
        """Return cached events from the local configuration directory."""

        cached_items = load_event_cache()
        cached_events: list[CalendarEvent] = []

        for item in cached_items:
            cached_event = self._deserialize_cached_event(item)
            if cached_event is not None:
                cached_events.append(cached_event)

        return cached_events

    def _build_fallback_result(self, error: Exception) -> CalendarSyncResult:
        """Build a non-fatal UI result when sync cannot reach Google."""

        cached_events = self._load_cached_events()
        is_network_error = self._is_network_error(error)

        if cached_events:
            status_message = "Usando caché." if not is_network_error else "Sin conexión • usando caché."
            return CalendarSyncResult(
                events=cached_events,
                status_message=status_message,
                is_from_cache=True,
            )

        if is_network_error:
            return CalendarSyncResult(
                events=[],
                status_message="Sin conexión.",
                is_from_cache=False,
            )

        return CalendarSyncResult(
            events=[],
            status_message="No se pudo sincronizar.",
            is_from_cache=False,
        )

    def _is_network_error(self, error: Exception) -> bool:
        """Detect common offline failures such as DNS or timeout issues."""

        network_errors = (
            TimeoutError,
            socket.timeout,
            socket.gaierror,
            ConnectionError,
            OSError,
            ServerNotFoundError,
        )
        if isinstance(error, network_errors):
            return True

        if isinstance(error, HttpError):
            return error.resp.status in {408, 429, 500, 502, 503, 504}

        return False
