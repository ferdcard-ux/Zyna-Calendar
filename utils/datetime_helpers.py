"""Date parsing and formatting helpers."""

from __future__ import annotations

from datetime import datetime


def format_event_datetime(value: datetime, is_all_day: bool) -> str:
    """Format an event start date for compact display in the widget."""

    if is_all_day:
        return value.strftime("%a %d %b • Todo el dia")

    return value.strftime("%a %d %b • %H:%M")
