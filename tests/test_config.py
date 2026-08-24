"""Tests for local settings normalization and migrations."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils import config as config_module


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point all config paths at an isolated temporary directory."""

    config_module.CONFIG_DIR = tmp_path
    config_module.SETTINGS_PATH = tmp_path / "settings.json"
    config_module.TOKEN_PATH = tmp_path / "token.json"
    config_module.EVENT_CACHE_PATH = tmp_path / "events_cache.json"
    config_module.LOG_PATH = tmp_path / "app.log"
    config_module.AUTOSTART_PATH = tmp_path / "autostart" / "zyna-calendar.desktop"
    monkeypatch.setattr("utils.config.ensure_config_dir", lambda: tmp_path)


def test_load_settings_creates_defaults(isolated_config: None) -> None:
    settings = config_module.load_settings()

    assert settings["refresh_interval"] == 15
    assert settings["max_events"] == 5
    assert settings["update_repo"] == ""
    assert settings["update_auto_check"] is True
    assert "refresh_interval_minutes" not in settings


def test_load_settings_migrates_legacy_key(isolated_config: None) -> None:
    config_module.SETTINGS_PATH.write_text(
        '{"refresh_interval_minutes": 120}',
        encoding="utf-8",
    )

    settings = config_module.load_settings()

    assert settings["refresh_interval"] == 120
    assert "refresh_interval_minutes" not in settings


def test_load_settings_clamps_values(isolated_config: None) -> None:
    config_module.SETTINGS_PATH.write_text(
        '{"max_events": 99, "refresh_interval": -5}',
        encoding="utf-8",
    )

    settings = config_module.load_settings()

    assert settings["max_events"] == 8
    assert settings["refresh_interval"] == 0


def test_load_settings_rejects_garbage_values(isolated_config: None) -> None:
    config_module.SETTINGS_PATH.write_text(
        '{"max_events": "abc", "window_width": null}',
        encoding="utf-8",
    )

    settings = config_module.load_settings()

    assert settings["max_events"] == 5
    assert settings["window_width"] == 340


@pytest.mark.parametrize(
    ("raw_repo", "expected"),
    [
        ("ferdcard/zyna-calendar", "ferdcard/zyna-calendar"),
        ("github.com/ferdcard/zyna-calendar", "ferdcard/zyna-calendar"),
        ("https://github.com/ferdcard/zyna-calendar/", "ferdcard/zyna-calendar"),
        ("https://api.github.com/repos/ferdcard/zyna-calendar", "ferdcard/zyna-calendar"),
        ("solo-usuario", ""),
        ("", ""),
        (123, ""),
    ],
)
def test_merge_update_repo_normalizes(
    isolated_config: None, raw_repo: object, expected: str
) -> None:
    settings = {"update_repo": raw_repo}

    assert config_module.merge_update_repo(settings, "update_repo", "") == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("yes", True),
        ("1", True),
        ("0", False),
        ("off", False),
        (None, True),
        ("random", True),
    ],
)
def test_merge_bool_coerces(isolated_config: None, raw_value: object, expected: bool) -> None:
    settings = {"update_auto_check": raw_value}

    assert config_module.merge_bool(settings, "update_auto_check", True) is expected


def test_load_settings_sanitizes_update_keys(isolated_config: None) -> None:
    config_module.SETTINGS_PATH.write_text(
        '{"update_repo": "https://github.com/ferdcard/zyna-calendar/", "update_auto_check": "off"}',
        encoding="utf-8",
    )

    settings = config_module.load_settings()

    assert settings["update_repo"] == "ferdcard/zyna-calendar"
    assert settings["update_auto_check"] is False


def test_save_window_position_roundtrip(isolated_config: None) -> None:
    result = config_module.save_window_position(120, 340)

    assert result["window_x"] == 120
    assert result["window_y"] == 340
    reloaded = config_module.load_settings()
    assert reloaded["window_x"] == 120
    assert reloaded["window_y"] == 340


def test_load_settings_clamps_opacity(isolated_config: None) -> None:
    config_module.SETTINGS_PATH.write_text('{"opacity": 5, "theme": "unknown"}', encoding="utf-8")

    settings = config_module.load_settings()

    assert settings["opacity"] == config_module.MIN_OPACITY
    assert settings["theme"] == config_module.DEFAULT_THEME_KEY


def test_load_settings_keeps_custom_hex(isolated_config: None) -> None:
    config_module.SETTINGS_PATH.write_text(
        '{"opacity": 90, "theme": "custom", "theme_bg_color": "#123abc",'
        ' "theme_card_color": "invalid", "theme_text_color": "#ffffff",'
        ' "theme_accent_color": "#3572b6"}',
        encoding="utf-8",
    )

    settings = config_module.load_settings()

    assert settings["opacity"] == 90
    assert settings["theme"] == "custom"
    assert settings["theme_bg_color"] == "#123ABC"
    assert settings["theme_card_color"] == config_module.THEMES["classic"]["card"]


def test_theme_palette_follows_preset() -> None:
    settings = {"theme": "ocean"}

    palette = config_module.get_theme_palette(settings)

    assert palette["bg"] == config_module.THEMES["ocean"]["bg"]
    assert palette["card"] == config_module.THEMES["ocean"]["card"]
    assert palette["accent"] == config_module.THEMES["ocean"]["accent"]


def test_theme_palette_uses_custom_colors() -> None:
    settings = {
        "theme": "custom",
        "theme_bg_color": "#101010",
        "theme_card_color": "#202020",
        "theme_text_color": "#FFFFFF",
        "theme_accent_color": "#00AAFF",
    }

    palette = config_module.get_theme_palette(settings)

    assert palette["bg"] == "#101010"
    assert palette["card"] == "#202020"
    assert palette["accent"] == "#00AAFF"


def test_theme_palette_fixes_poor_text_contrast() -> None:
    settings = {
        "theme": "custom",
        "theme_bg_color": "#FFFFFF",
        "theme_card_color": "#EEEEEE",
        "theme_text_color": "#FFFFFF",
        "theme_accent_color": "#3572B6",
    }

    palette = config_module.get_theme_palette(settings)

    assert palette["text"] != "#FFFFFF"


def test_contrast_ratio_is_wcag() -> None:
    assert config_module.contrast_ratio("#FFFFFF", "#000000") > 15
    assert config_module.contrast_ratio("#FFFFFF", "#FFFFFF") == 1.0
    assert config_module.readable_text_color("#000000") == "#FFFFFF"


def test_rgba_string_builds_css() -> None:
    assert config_module.rgba_string("#3572B6", 120) == "rgba(53, 114, 182, 120)"


def test_hex_to_rgb_parses() -> None:
    assert config_module.hex_to_rgb("#3572B6") == (53, 114, 182)


def test_load_settings_recovers_from_corrupt_file(isolated_config, tmp_path: Path) -> None:
    config_module.SETTINGS_PATH.write_text("{not valid json", encoding="utf-8")

    settings = config_module.load_settings()

    assert settings["refresh_interval"] == 15
    assert config_module.SETTINGS_PATH.exists()
    assert Path(str(config_module.SETTINGS_PATH) + ".corrupt").exists()


def test_save_event_cache_is_atomic(isolated_config) -> None:
    config_module.save_event_cache([{"event_id": "1"}])

    snapshot = config_module.load_event_cache_snapshot()
    assert snapshot["events"] == [{"event_id": "1"}]
    assert snapshot["saved_at"]


def test_notification_state_roundtrip(isolated_config) -> None:
    config_module.save_notification_state({"evt-a", "evt-b"}, {"evt-c"})

    state = config_module.load_notification_state()
    assert state["notified_today"] == ["evt-a", "evt-b"]
    assert state["notified_upcoming"] == ["evt-c"]

    empty = {"date": "", "notified_today": [], "notified_upcoming": []}
    assert set(empty) == set(state)
