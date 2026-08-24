"""Tests for the OAuth2 auth layer and launcher exit-code contract."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from core.auth import (
    TOKEN_STATE_MISSING,
    TOKEN_STATE_NETWORK,
    TOKEN_STATE_NO_REFRESH,
    TOKEN_STATE_OK,
    TOKEN_STATE_REVOKED,
    MissingCredentialsError,
    _persist_credentials,
    complete_manual_auth,
    init_manual_auth,
    launcher_exit_code,
    load_google_credentials,
    probe_token_state,
)


@pytest.fixture()
def token_path(tmp_path: Path) -> Path:
    """Return a token path inside an isolated temp directory."""

    return tmp_path / "token.json"


def write_token(
    path: Path, *, refresh_token: str | None = "refresh-123", expired: bool = True
) -> None:
    payload: dict[str, object] = {
        "token": "access-xyz" if expired else "access-ok",
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-test",
        "client_secret": "secret-test",
        "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
    }
    if refresh_token is None:
        payload["refresh_token"] = ""
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_probe_missing_token(token_path: Path) -> None:
    with patch("core.auth.get_token_path", return_value=token_path):
        assert probe_token_state() == TOKEN_STATE_MISSING


def test_probe_no_refresh_token(token_path: Path) -> None:
    write_token(token_path, refresh_token=None)
    with patch("core.auth.get_token_path", return_value=token_path):
        assert probe_token_state() == TOKEN_STATE_NO_REFRESH


def test_probe_valid_token_does_not_refresh(token_path: Path) -> None:
    write_token(token_path, expired=False)
    fake_creds = MagicMock()
    fake_creds.expired = False
    fake_creds.refresh_token = "refresh-123"

    with patch("core.auth.Credentials.from_authorized_user_file", return_value=fake_creds):
        assert probe_token_state(token_path) == TOKEN_STATE_OK


def test_probe_revoked_token(token_path: Path) -> None:
    write_token(token_path, expired=True)
    fake_creds = MagicMock()
    fake_creds.expired = True
    fake_creds.token = "access-xyz"
    fake_creds.refresh_token = "refresh-123"
    fake_creds.refresh.side_effect = RefreshError("invalid_grant: revoked")

    with patch("core.auth.Credentials.from_authorized_user_file", return_value=fake_creds):
        result = probe_token_state(token_path)

    assert result == TOKEN_STATE_REVOKED


def test_probe_network_error_token(token_path: Path) -> None:
    write_token(token_path, expired=True)
    fake_creds = MagicMock()
    fake_creds.expired = True
    fake_creds.token = "access-xyz"
    fake_creds.refresh_token = "refresh-123"
    fake_creds.refresh.side_effect = TimeoutError()

    with patch("core.auth.Credentials.from_authorized_user_file", return_value=fake_creds):
        assert probe_token_state(token_path) == TOKEN_STATE_NETWORK


def test_launcher_exit_codes() -> None:
    assert launcher_exit_code(TOKEN_STATE_OK) == 0
    assert launcher_exit_code(TOKEN_STATE_MISSING) == 10
    assert launcher_exit_code(TOKEN_STATE_NO_REFRESH) == 11
    assert launcher_exit_code(TOKEN_STATE_REVOKED) == 20
    assert launcher_exit_code(TOKEN_STATE_NETWORK) == 30
    assert launcher_exit_code("unknown") == 0


def test_init_manual_auth_requires_credentials(tmp_path: Path) -> None:
    missing = tmp_path / "credentials.json"
    with (
        patch("core.auth.get_credentials_path", return_value=missing),
        pytest.raises(MissingCredentialsError),
    ):
        init_manual_auth()


def test_complete_manual_auth_requires_credentials(tmp_path: Path) -> None:
    missing = tmp_path / "credentials.json"
    with (
        patch("core.auth.get_credentials_path", return_value=missing),
        pytest.raises(MissingCredentialsError),
    ):
        complete_manual_auth(code="any-code")


def test_manual_redirect_uri_is_not_oob() -> None:
    from core.auth import MANUAL_REDIRECT_URI

    assert "oob" not in MANUAL_REDIRECT_URI
    assert MANUAL_REDIRECT_URI.startswith("http://localhost")


def test_init_manual_auth_uses_loopback_redirect(tmp_path: Path) -> None:
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text("{}", encoding="utf-8")

    with patch(
        "core.auth.get_credentials_path",
        return_value=credentials_file,
    ), patch("core.auth.InstalledAppFlow") as fake_flow_module:
        fake_flow = fake_flow_module.from_client_secrets_file.return_value
        fake_flow.authorization_url.return_value = ("https://example.com/auth", "state")

        _, auth_url = init_manual_auth()

    assert fake_flow.redirect_uri == "http://localhost:1"
    assert auth_url == "https://example.com/auth"


def _real_expired_credentials() -> Credentials:
    return Credentials(
        token="access-xyz",
        refresh_token="refresh-123",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-test",
        client_secret="secret-test",
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )


def test_load_credentials_returns_cached_on_network_error(token_path: Path) -> None:
    write_token(token_path, expired=True)

    with (
        patch("core.auth.get_token_path", return_value=token_path),
        patch(
            "core.auth.Request",
        ), patch.object(
            Credentials,
            "refresh",
            side_effect=OSError("network down"),
        ),
    ):
        loaded = load_google_credentials()

    assert isinstance(loaded, Credentials)
    assert loaded.refresh_token == "refresh-123"


def test_load_credentials_forces_reauth_on_revoked(token_path: Path) -> None:
    write_token(token_path, expired=True)
    fresh = MagicMock()
    fresh.valid = True

    with (
        patch("core.auth.get_token_path", return_value=token_path),
        patch("core.auth._has_display", return_value=False),
        patch(
            "core.auth.Request",
        ), patch.object(
            Credentials,
            "refresh",
            side_effect=RefreshError("invalid_grant"),
        ),
        patch("core.auth.complete_manual_auth", return_value=fresh) as fake_complete,
    ):
        loaded = load_google_credentials()

    assert loaded is fresh
    fake_complete.assert_called_once()


def test_load_credentials_prefers_loopback_when_graphical(token_path: Path) -> None:
    write_token(token_path, expired=True)
    fresh = MagicMock()
    fresh.valid = True

    with (
        patch("core.auth.get_token_path", return_value=token_path),
        patch("core.auth._has_display", return_value=True),
        patch(
            "core.auth.Request",
        ), patch.object(
            Credentials,
            "refresh",
            side_effect=RefreshError("invalid_grant"),
        ),
        patch("core.auth.run_loopback_auth", return_value=fresh) as fake_loopback,
    ):
        loaded = load_google_credentials(force_reauth=True)

    assert loaded is fresh
    fake_loopback.assert_called_once()


def test_persist_credentials_sets_owner_only_permissions(tmp_path: Path) -> None:
    import stat

    target = tmp_path / "token.json"
    fake_creds = MagicMock()
    del fake_creds.to_json
    del fake_creds.to_authorized_user_info
    fake_creds.token = "access"
    fake_creds.refresh_token = "refresh"
    fake_creds.token_uri = "https://oauth2.googleapis.com/token"
    fake_creds.client_id = "id"
    fake_creds.client_secret = "secret"
    fake_creds.scopes = ["scope"]

    _persist_credentials(target, fake_creds)

    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600
