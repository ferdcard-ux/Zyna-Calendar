"""Tests for the Google Calendar service layer."""

from __future__ import annotations

import json
import socket
from datetime import date, datetime, time, timedelta

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import ServerNotFoundError

from core.calendar_service import (
    LOCAL_TIMEZONE,
    MAX_EVENTS_LIMIT,
    CalendarClient,
    CalendarSyncResult,
)


def _make_client() -> CalendarClient:
    """Build a client that never hits a real network service."""

    return CalendarClient(credentials=None)  # type: ignore[arg-type]


def test_max_results_is_clamped() -> None:
    client = _make_client()

    assert client._clamp_max_results(99) == MAX_EVENTS_LIMIT
    assert client._clamp_max_results(0) == 1
    assert client._clamp_max_results(3) == 3


def test_parse_timed_start() -> None:
    client = _make_client()

    start_at, is_all_day = client._parse_event_start(
        {"dateTime": "2026-08-12T09:30:00-05:00"},
    )

    assert is_all_day is False
    assert start_at.tzinfo is not None


def test_parse_utc_start_normalized() -> None:
    client = _make_client()

    start_at, is_all_day = client._parse_event_start(
        {"dateTime": "2026-08-12T14:30:00Z"},
    )

    assert is_all_day is False
    assert start_at.utcoffset() is not None
    assert start_at.hour == 9  # UTC -05:00 (America/Bogota)


def test_parse_all_day_start() -> None:
    client = _make_client()

    start_at, is_all_day = client._parse_event_start({"date": "2026-12-25"})

    assert is_all_day is True
    assert start_at == datetime.combine(date(2026, 12, 25), time.min, tzinfo=LOCAL_TIMEZONE)


def test_deserialize_event() -> None:
    client = _make_client()

    event = client._deserialize_event(
        {
            "id": "abc123",
            "summary": "Reunion",
            "start": {"dateTime": "2026-08-13T10:00:00-05:00"},
            "htmlLink": "https://calendar.google.com/event?id=abc123",
        }
    )

    assert event.event_id == "abc123"
    assert event.title == "Reunion"
    assert event.is_all_day is False
    assert event.html_link.startswith("https://")


def test_deserialize_event_default_title() -> None:
    client = _make_client()

    event = client._deserialize_event({"id": "x", "start": {"date": "2026-08-13"}})

    assert event.title == "Sin titulo"


def test_is_network_error_detects_dns() -> None:
    client = _make_client()

    assert (
        client._is_network_error(socket.gaierror(-3, "Fallo temporal en la resolucion del nombre"))
        is True
    )
    assert client._is_network_error(ServerNotFoundError()) is True
    assert client._is_network_error(TimeoutError()) is True


def test_is_auth_error_detects_refresh_failure() -> None:
    client = _make_client()

    assert client._is_auth_error(Exception("token has been revoked")) is False
    assert client._is_auth_error(socket.gaierror(-3, "dns")) is False


def test_build_fallback_without_cache_reports_network() -> None:
    client = _make_client()
    client._load_cached_events = lambda: []  # type: ignore[method-assign]
    client._load_cached_timestamp = lambda: None  # type: ignore[method-assign]

    result: CalendarSyncResult = client._build_fallback_result(socket.gaierror(-3, "DNS failure"))

    assert result.events == []
    assert result.is_from_cache is False
    assert result.requires_attention is True
    status_lower = result.status_message.lower()
    assert "conexión" in status_lower or "conexion" in status_lower


def test_build_fallback_with_cache_uses_it() -> None:
    client = _make_client()
    client._load_cached_events = lambda: []  # type: ignore[method-assign]
    client._load_cached_timestamp = lambda: datetime.now(LOCAL_TIMEZONE) - timedelta(hours=2)  # type: ignore[method-assign]

    result: CalendarSyncResult = client._build_fallback_result(socket.gaierror(-3, "DNS failure"))

    assert result.requires_attention is True


def test_http_error_status_detection() -> None:
    client = _make_client()

    assert client._is_network_error(_fake_http_error(503)) is True
    assert client._is_network_error(_fake_http_error(404)) is False
    assert client._is_auth_error(_fake_http_error(403)) is True


def _fake_http_error(status: int) -> HttpError:
    return HttpError(_FakeResponse(status), b"{}", uri="https://example.com")


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "fake"


def test_invalidate_clears_cached_service_and_credentials() -> None:
    client = CalendarClient(credentials=object())  # type: ignore[arg-type]
    client._service = object()  # type: ignore[assignment]

    client.invalidate()

    assert client._service is None
    assert client._credentials is None


def test_fallback_result_uses_cache(monkeypatch, tmp_path) -> None:
    from utils import config as config_module

    payload = {
        "saved_at": "2026-08-20T12:00:00+00:00",
        "events": [
            {
                "event_id": "evt-1",
                "title": "Cacheado",
                "start_at": "2026-08-21T10:00:00-05:00",
                "is_all_day": False,
                "html_link": "",
            }
        ],
    }
    cache_path = tmp_path / "events_cache.json"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(config_module, "get_event_cache_path", lambda: cache_path)

    client = _make_client()
    result = client.fallback_result(RefreshError("invalid_grant"))

    assert result.is_from_cache is True
    assert result.requires_attention is True
    assert len(result.events) == 1
    assert result.events[0].title == "Cacheado"
