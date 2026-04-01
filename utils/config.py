"""Helpers for local configuration management."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_SLUG = "zyna-calendar"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path.home() / ".config" / APP_SLUG
SETTINGS_PATH = CONFIG_DIR / "settings.json"
TOKEN_PATH = CONFIG_DIR / "token.json"
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
EVENT_CACHE_PATH = CONFIG_DIR / "events_cache.json"
LOG_PATH = CONFIG_DIR / "app.log"
AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "zyna-calendar.desktop"
APP_ICON_PATH = PROJECT_ROOT / "icon-128x128.png"

DEFAULT_SETTINGS: dict[str, Any] = {
    "window_x": 40,
    "window_y": 40,
    "window_width": 340,
    "window_height": 430,
    "refresh_interval_minutes": 15,
    "refresh_interval": 15,
    "max_events": 5,
    "calendar_id": "primary",
    "credentials_path": str(CREDENTIALS_PATH),
    "autostart_enabled": False,
}


def ensure_config_dir() -> Path:
    """Create the local configuration directory if needed."""

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def get_settings_path() -> Path:
    """Return the settings file path inside the local config directory."""

    ensure_config_dir()
    return SETTINGS_PATH


def get_token_path() -> Path:
    """Return the cached OAuth token file path."""

    ensure_config_dir()
    return TOKEN_PATH


def get_credentials_path() -> Path:
    """Return the expected project path for Google OAuth credentials."""

    settings = load_settings()
    configured_path = settings.get("credentials_path")
    if configured_path:
        return Path(configured_path)

    return CREDENTIALS_PATH


def get_autostart_path() -> Path:
    """Return the autostart desktop file path."""

    return AUTOSTART_PATH


def get_app_icon_path() -> Path:
    """Return the icon path used by the widget and dialogs."""

    return APP_ICON_PATH


def load_settings() -> dict[str, Any]:
    """Load widget settings and create the default file on first run."""

    settings_path = get_settings_path()

    if not settings_path.exists():
        save_settings(DEFAULT_SETTINGS)
        return deepcopy(DEFAULT_SETTINGS)

    with settings_path.open("r", encoding="utf-8") as file_pointer:
        loaded_settings = json.load(file_pointer)

    merged_settings = deepcopy(DEFAULT_SETTINGS)
    merged_settings.update(loaded_settings)
    if "refresh_interval" not in merged_settings and "refresh_interval_minutes" in merged_settings:
        merged_settings["refresh_interval"] = merged_settings["refresh_interval_minutes"]
    return merged_settings


def save_settings(settings: dict[str, Any]) -> None:
    """Persist widget settings in the local configuration directory."""

    settings_path = get_settings_path()
    with settings_path.open("w", encoding="utf-8") as file_pointer:
        json.dump(settings, file_pointer, indent=4)


def save_window_position(window_x: int, window_y: int) -> dict[str, Any]:
    """Persist the last widget coordinates and return updated settings."""

    settings = load_settings()
    settings["window_x"] = int(window_x)
    settings["window_y"] = int(window_y)
    save_settings(settings)
    return settings


def get_event_cache_path() -> Path:
    """Return the cache file used to persist the last successful events."""

    ensure_config_dir()
    return EVENT_CACHE_PATH


def load_event_cache() -> list[dict[str, Any]]:
    """Load the cached event payload or return an empty list."""

    cache_path = get_event_cache_path()
    if not cache_path.exists():
        return []

    try:
        with cache_path.open("r", encoding="utf-8") as file_pointer:
            payload = json.load(file_pointer)
    except (json.JSONDecodeError, OSError):
        return []

    if isinstance(payload, dict):
        events = payload.get("events", [])
        if isinstance(events, list):
            return events

    return []


def save_event_cache(events: list[dict[str, Any]]) -> None:
    """Persist the latest successful event payload to disk."""

    cache_path = get_event_cache_path()
    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "events": events,
    }
    with cache_path.open("w", encoding="utf-8") as file_pointer:
        json.dump(payload, file_pointer, indent=4)


def get_log_path() -> Path:
    """Return the application log path inside the local config directory."""

    ensure_config_dir()
    return LOG_PATH


def configure_logging() -> logging.Logger:
    """Configure a quiet file logger for the application."""

    log_path = get_log_path()
    logger = logging.getLogger(APP_SLUG)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == log_path
        for handler in logger.handlers
    ):
        return logger

    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(file_handler)
    return logger
