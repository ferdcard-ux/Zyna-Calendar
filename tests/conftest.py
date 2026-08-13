"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _patch_config_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect every config file to an isolated temp directory per test."""

    from utils import config as config_module

    config_module.CONFIG_DIR = tmp_path
    config_module.SETTINGS_PATH = tmp_path / "settings.json"
    config_module.TOKEN_PATH = tmp_path / "token.json"
    config_module.EVENT_CACHE_PATH = tmp_path / "events_cache.json"
    config_module.LOG_PATH = tmp_path / "app.log"
    config_module.AUTOSTART_PATH = tmp_path / "autostart" / "zyna-calendar.desktop"

    # Rebind module-level path getters that capture the paths at import time.
    monkeypatch.setattr(config_module, "get_settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(config_module, "get_token_path", lambda: tmp_path / "token.json")
    cache_path = tmp_path / "events_cache.json"
    monkeypatch.setattr(config_module, "get_event_cache_path", lambda: cache_path)
    monkeypatch.setattr(config_module, "get_log_path", lambda: tmp_path / "app.log")
    autostart_dir = tmp_path / "autostart"
    autostart_file = autostart_dir / "zyna-calendar.desktop"
    monkeypatch.setattr(config_module, "get_autostart_path", lambda: autostart_file)
    monkeypatch.setattr(config_module, "ensure_config_dir", lambda: tmp_path)

    def _get_credentials_path() -> Path:
        settings = config_module.load_settings()
        configured_path = settings.get("credentials_path")
        if configured_path:
            return Path(configured_path)
        return PROJECT_ROOT / "credentials.json"

    monkeypatch.setattr(config_module, "get_credentials_path", _get_credentials_path)
