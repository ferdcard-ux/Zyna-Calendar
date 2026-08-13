"""Helpers for local configuration management."""

from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_SLUG = "zyna-calendar"
APP_VERSION = "0.1.8"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path.home() / ".config" / APP_SLUG
SETTINGS_PATH = CONFIG_DIR / "settings.json"
TOKEN_PATH = CONFIG_DIR / "token.json"
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
EVENT_CACHE_PATH = CONFIG_DIR / "events_cache.json"
LOG_PATH = CONFIG_DIR / "app.log"
AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "zyna-calendar.desktop"
APP_ICON_PATH = PROJECT_ROOT / "icon-128x128.png"

MIN_OPACITY = 30
MAX_OPACITY = 100
DEFAULT_OPACITY = 78
MIN_CONTRAST_RATIO = 3.0
CUSTOM_THEME_KEY = "custom"
DEFAULT_THEME_KEY = "classic"

THEMES: dict[str, dict[str, str]] = {
    "classic": {
        "name": "Clasico Azul",
        "bg": "#1E232D",
        "card": "#2C3340",
        "text": "#FFFFFF",
        "accent": "#3572B6",
    },
    "midnight": {
        "name": "Medianoche Violeta",
        "bg": "#1A1A2E",
        "card": "#2A2A4A",
        "text": "#F3F0FF",
        "accent": "#9C6ADE",
    },
    "forest": {
        "name": "Bosque Verde",
        "bg": "#0F2B1E",
        "card": "#1A3D2C",
        "text": "#E8F5E9",
        "accent": "#4CAF50",
    },
    "ocean": {
        "name": "Oceano Azul",
        "bg": "#0E2A3A",
        "card": "#17475F",
        "text": "#E3F2FD",
        "accent": "#42A5F5",
    },
    "ember": {
        "name": "Llamarada Naranja",
        "bg": "#2B1A0E",
        "card": "#452D18",
        "text": "#FFF3E0",
        "accent": "#FF9800",
    },
    "rose": {
        "name": "Rosa Suave",
        "bg": "#2E1420",
        "card": "#4A2236",
        "text": "#FCE4EC",
        "accent": "#F06292",
    },
    "graphite": {
        "name": "Grafito Neutro",
        "bg": "#20262C",
        "card": "#2F3740",
        "text": "#ECEFF1",
        "accent": "#78909C",
    },
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "window_x": 40,
    "window_y": 40,
    "window_width": 340,
    "window_height": 430,
    "refresh_interval": 15,
    "max_events": 5,
    "calendar_id": "primary",
    "credentials_path": str(CREDENTIALS_PATH),
    "autostart_enabled": False,
    "theme": DEFAULT_THEME_KEY,
    "opacity": DEFAULT_OPACITY,
    "theme_bg_color": THEMES[DEFAULT_THEME_KEY]["bg"],
    "theme_card_color": THEMES[DEFAULT_THEME_KEY]["card"],
    "theme_text_color": THEMES[DEFAULT_THEME_KEY]["text"],
    "theme_accent_color": THEMES[DEFAULT_THEME_KEY]["accent"],
    "update_repo": "",
    "update_auto_check": True,
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

    migrated_settings = _migrate_settings(loaded_settings)
    merged_settings = deepcopy(DEFAULT_SETTINGS)
    merged_settings.update(migrated_settings)
    return _sanitize_settings(merged_settings)


def _migrate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Apply one-time migrations for legacy settings keys."""

    if "refresh_interval" not in settings and "refresh_interval_minutes" in settings:
        settings["refresh_interval"] = settings.pop("refresh_interval_minutes")
    settings.pop("refresh_interval_minutes", None)
    return settings


def _sanitize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Clamp user settings into their valid ranges."""

    window_x = merge_int(settings, "window_x", DEFAULT_SETTINGS["window_x"], -20000, 20000)
    window_y = merge_int(settings, "window_y", DEFAULT_SETTINGS["window_y"], -20000, 20000)
    width = merge_int(settings, "window_width", DEFAULT_SETTINGS["window_width"], 240, 1200)
    height = merge_int(settings, "window_height", DEFAULT_SETTINGS["window_height"], 200, 1200)
    refresh = merge_int(settings, "refresh_interval", DEFAULT_SETTINGS["refresh_interval"], 0, 1440)
    events = merge_int(settings, "max_events", DEFAULT_SETTINGS["max_events"], 1, 8)
    opacity = merge_int(settings, "opacity", DEFAULT_OPACITY, MIN_OPACITY, MAX_OPACITY)
    theme = merge_theme(settings, "theme", DEFAULT_THEME_KEY)
    bg_color = merge_hex(settings, "theme_bg_color", THEMES[DEFAULT_THEME_KEY]["bg"])
    card_color = merge_hex(settings, "theme_card_color", THEMES[DEFAULT_THEME_KEY]["card"])
    text_color = merge_hex(settings, "theme_text_color", THEMES[DEFAULT_THEME_KEY]["text"])
    accent_color = merge_hex(settings, "theme_accent_color", THEMES[DEFAULT_THEME_KEY]["accent"])
    update_repo = merge_update_repo(settings, "update_repo", "")
    update_auto_check = merge_bool(settings, "update_auto_check", True)

    settings["window_x"] = window_x
    settings["window_y"] = window_y
    settings["window_width"] = width
    settings["window_height"] = height
    settings["refresh_interval"] = refresh
    settings["max_events"] = events
    settings["opacity"] = opacity
    settings["theme"] = theme
    settings["theme_bg_color"] = bg_color
    settings["theme_card_color"] = card_color
    settings["theme_text_color"] = text_color
    settings["theme_accent_color"] = accent_color
    settings["update_repo"] = update_repo
    settings["update_auto_check"] = update_auto_check
    return settings


def merge_theme(settings: dict[str, Any], key: str, default: str) -> str:
    """Return a valid theme key or the fallback default."""

    value = settings.get(key)
    if isinstance(value, str) and (value in THEMES or value == CUSTOM_THEME_KEY):
        return value
    return default


def merge_hex(settings: dict[str, Any], key: str, default: str) -> str:
    """Return a normalized hex color from settings or the fallback default."""

    value = settings.get(key)
    if isinstance(value, str) and _is_valid_hex(value):
        return value.upper()
    return default


def _is_valid_hex(value: str) -> bool:
    """Return True for canonical ``#RRGGBB`` colors."""

    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", value))


def _clamp_int(value: Any, default: int, lower: int, upper: int) -> int:
    """Coerce a value to an integer constrained to a range."""

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(lower, min(upper, parsed))


def merge_int(settings: dict[str, Any], key: str, default: int, lower: int, upper: int) -> int:
    """Clamp a settings value with its default as the fallback."""

    return _clamp_int(settings.get(key), default, lower, upper)


def merge_bool(settings: dict[str, Any], key: str, default: bool) -> bool:
    """Coerce a settings value into a boolean with a fallback default."""

    value = settings.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return default


def merge_update_repo(settings: dict[str, Any], key: str, default: str) -> str:
    """Return a normalized ``owner/repo`` update source or the fallback default."""

    value = settings.get(key)
    if not isinstance(value, str):
        return default
    repo = value.strip().strip("/")
    repo = repo.removeprefix("https://github.com/")
    repo = repo.removeprefix("https://api.github.com/repos/")
    repo = repo.removeprefix("github.com/")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        return repo
    return default


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

    snapshot = load_event_cache_snapshot()
    events = snapshot.get("events", [])
    if isinstance(events, list):
        return events

    return []


def load_event_cache_snapshot() -> dict[str, Any]:
    """Load the full cache payload including metadata."""

    cache_path = get_event_cache_path()
    if not cache_path.exists():
        return {}

    try:
        with cache_path.open("r", encoding="utf-8") as file_pointer:
            payload = json.load(file_pointer)
    except (json.JSONDecodeError, OSError):
        return {}

    if isinstance(payload, dict):
        return payload

    return {}


def save_event_cache(events: list[dict[str, Any]]) -> None:
    """Persist the latest successful event payload to disk."""

    cache_path = get_event_cache_path()
    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "events": events,
    }
    with cache_path.open("w", encoding="utf-8") as file_pointer:
        json.dump(payload, file_pointer, indent=4)


def get_theme_palette(settings: dict[str, Any]) -> dict[str, str]:
    """Resolve the active color palette honoring a custom theme."""

    theme_key = settings.get("theme", DEFAULT_THEME_KEY)
    if theme_key == CUSTOM_THEME_KEY:
        palette = {
            "bg": settings.get("theme_bg_color", THEMES[DEFAULT_THEME_KEY]["bg"]),
            "card": settings.get("theme_card_color", THEMES[DEFAULT_THEME_KEY]["card"]),
            "text": settings.get("theme_text_color", THEMES[DEFAULT_THEME_KEY]["text"]),
            "accent": settings.get("theme_accent_color", THEMES[DEFAULT_THEME_KEY]["accent"]),
        }
    else:
        palette = dict(THEMES.get(theme_key, THEMES[DEFAULT_THEME_KEY]))

    palette["text"] = ensure_text_contrast(palette["bg"], palette["text"])
    return palette


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert a ``#RRGGBB`` string into an RGB tuple."""

    normalized = value.lstrip("#")
    if len(normalized) != 6:
        return (0, 0, 0)
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def rgba_string(value: str, alpha: int) -> str:
    """Build a CSS rgba() string from a hex color and an alpha channel."""

    red, green, blue = hex_to_rgb(value)
    clamped_alpha = max(0, min(255, int(alpha)))
    return f"rgba({red}, {green}, {blue}, {clamped_alpha})"


def _linearize_channel(channel: float) -> float:
    """Convert a single sRGB channel into its linear value."""

    if channel <= 0.03928:
        return channel / 12.92
    exponent: float = 2.4
    return float(((channel + 0.055) / 1.055) ** exponent)


def relative_luminance(value: str) -> float:
    """Return the WCAG relative luminance of a hex color."""

    red, green, blue = hex_to_rgb(value)
    linear_channels = tuple(_linearize_channel(channel / 255) for channel in (red, green, blue))
    return 0.2126 * linear_channels[0] + 0.7152 * linear_channels[1] + 0.0722 * linear_channels[2]


def contrast_ratio(first: str, second: str) -> float:
    """Return the WCAG contrast ratio between two hex colors."""

    first_luminance = relative_luminance(first)
    second_luminance = relative_luminance(second)
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def readable_text_color(background: str) -> str:
    """Return black or white depending on which offers the better contrast."""

    white_ratio = contrast_ratio(background, "#FFFFFF")
    black_ratio = contrast_ratio(background, "#000000")
    return "#FFFFFF" if white_ratio >= black_ratio else "#000000"


def ensure_text_contrast(background: str, text: str) -> str:
    """Swap to black/white text when the requested text lacks enough contrast."""

    if contrast_ratio(background, text) >= MIN_CONTRAST_RATIO:
        return text
    return readable_text_color(background)


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
        isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path
        for handler in logger.handlers
    ):
        return logger

    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(file_handler)
    return logger
