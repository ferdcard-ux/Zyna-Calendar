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

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.auth import MissingCredentialsError, load_google_credentials  # noqa: E402
from core.calendar_service import CalendarClient  # noqa: E402
from ui.widget import CalendarWidget  # noqa: E402
from utils.config import configure_logging, load_settings  # noqa: E402


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

    settings = load_settings()
    calendar_client = CalendarClient(credentials=credentials)

    app = QApplication(sys.argv)
    widget = CalendarWidget(calendar_client=calendar_client, settings=settings)
    widget.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
