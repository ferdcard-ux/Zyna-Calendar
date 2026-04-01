#!/usr/bin/env python3
"""Application entry point for Zyna-Calendar."""

from __future__ import annotations

import os
import sys
import warnings

os.environ.setdefault("NO_AT_BRIDGE", "1")
os.environ.setdefault(
    "QT_LOGGING_RULES",
    "*.debug=false;qt.accessibility.atspi.warning=false",
)

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module="google.api_core._python_version_support",
)

from PyQt6.QtWidgets import QApplication

from core.auth import MissingCredentialsError, load_google_credentials
from core.calendar_service import CalendarClient
from ui.widget import CalendarWidget
from utils.config import configure_logging, load_settings


def main() -> int:
    """Start the PyQt application and show the calendar widget."""

    configure_logging()
    try:
        credentials = load_google_credentials()
    except MissingCredentialsError as error:
        print(f"Falta credentials.json: {error}")
        return 1
    except Exception as error:
        print(f"No se pudo completar la autenticación: {error}")
        return 1

    calendar_client = CalendarClient(credentials=credentials)

    app = QApplication(sys.argv)
    widget = CalendarWidget(
        events_provider=lambda: calendar_client.list_upcoming_events(
            calendar_id=load_settings()["calendar_id"],
            max_results=int(load_settings()["max_events"]),
        ),
        settings=load_settings(),
    )
    widget.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
