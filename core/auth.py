"""OAuth2 authentication helpers for Google Calendar."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from utils.config import get_credentials_path, get_token_path

SCOPES = ("https://www.googleapis.com/auth/calendar.readonly",)

#: Redirect URI for the manual copy/paste flow. The legacy OOB URI was removed
#: by Google in 2023; a loopback URL is the supported replacement.
MANUAL_REDIRECT_URI = "http://localhost:1"

#: Exit codes used by the Bash launcher to decide whether to open the reauth terminal.
TOKEN_STATE_OK = "ok"
TOKEN_STATE_MISSING = "missing"
TOKEN_STATE_NO_REFRESH = "no_refresh"
TOKEN_STATE_REVOKED = "revoked"
TOKEN_STATE_NETWORK = "network"

_LAUNCHER_EXIT_CODES = {
    TOKEN_STATE_OK: 0,
    TOKEN_STATE_MISSING: 10,
    TOKEN_STATE_NO_REFRESH: 11,
    TOKEN_STATE_REVOKED: 20,
    TOKEN_STATE_NETWORK: 30,
}


class MissingCredentialsError(FileNotFoundError):
    """Raised when the OAuth client credentials file is not available."""


def load_google_credentials(
    scopes: Sequence[str] | None = None,
    force_reauth: bool = False,
) -> Credentials:
    """Load Google credentials, refreshing or reauthorizing when needed."""

    requested_scopes = list(scopes or SCOPES)
    token_path = get_token_path()

    credentials = None if force_reauth else _load_cached_credentials(token_path, requested_scopes)

    # 1. Intenta refrescar si el token existe pero expiro.
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            _persist_credentials(token_path, credentials)
            return credentials
        except RefreshError:
            print("No se pudo refrescar el token. Se solicitará una nueva autorización.")
            credentials = None
        except Exception as error:
            # Fallo transitorio (red/DNS/timeout): no force re-auth; la sync caerá a caché.
            print(f"No se pudo refrescar el token por un error transitorio: {error}")
            return credentials

    # 2. Si no hay credenciales validas, autorizar vía navegador (loopback)
    #    y caer al modo manual copy/paste solo si no hay entorno gráfico.
    if not credentials or not credentials.valid:
        if _has_display():
            try:
                return run_loopback_auth(requested_scopes)
            except Exception as error:
                print(f"Flujo de navegador no disponible ({error}). Usando modo manual.")
        credentials = complete_manual_auth(scopes=requested_scopes)

    return credentials


def _has_display() -> bool:
    """Return True when a graphical session is available for the browser flow."""

    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def init_manual_auth(
    scopes: Sequence[str] | None = None,
) -> tuple[InstalledAppFlow, str]:
    """Build the manual copy/paste flow and return the authorization URL.

    Uses a loopback redirect URI instead of the deprecated OOB flow. Returns the
    fully configured flow plus the URL the user must open. The caller is
    responsible for finishing the exchange with :func:`complete_manual_auth`.
    """

    requested_scopes = list(scopes or SCOPES)
    credentials_path = get_credentials_path()

    if not credentials_path.exists():
        raise MissingCredentialsError(f"Falta credentials.json en {credentials_path}")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path),
        requested_scopes,
    )
    flow.redirect_uri = MANUAL_REDIRECT_URI

    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
    )
    return flow, auth_url


def run_loopback_auth(
    scopes: Sequence[str] | None = None,
    open_browser: bool = True,
) -> Credentials:
    """Run the automatic loopback OAuth flow and persist the new token.

    Starts an ephemeral local HTTP server, opens the browser, captures the
    authorization response and exchanges the code. Raises ``OSError``-like
    errors from the underlying server when no graphical/browser environment is
    available; callers should fall back to :func:`complete_manual_auth`.
    """

    requested_scopes = list(scopes or SCOPES)
    credentials_path = get_credentials_path()

    if not credentials_path.exists():
        raise MissingCredentialsError(f"Falta credentials.json en {credentials_path}")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path),
        requested_scopes,
    )
    flow_credentials = flow.run_local_server(port=0, open_browser=open_browser)
    if not isinstance(flow_credentials, Credentials):
        raise TypeError("El flujo de OAuth no devolvió credenciales válidas.")
    _persist_credentials(get_token_path(), flow_credentials)
    return flow_credentials


def complete_manual_auth(
    code: str | None = None,
    scopes: Sequence[str] | None = None,
) -> Credentials:
    """Run the manual copy/paste flow, optionally finishing with a pasted code.

    If ``code`` is provided the token exchange is completed immediately, otherwise
    the authorization URL is printed and the code is read from standard input.
    """

    requested_scopes = list(scopes or SCOPES)

    flow, auth_url = init_manual_auth(requested_scopes)

    if code is None:
        print(f"\n{'=' * 60}\nAUTORIZACIÓN REQUERIDA\n1. Abre: {auth_url}")
        print(f"2. Pega el codigo abajo\n{'=' * 60}")
        code = input("Código: ").strip()

    try:
        flow.fetch_token(code=code)
    except Exception as error:
        print("Autenticación fallida. El código es inválido o expirado.")
        raise error

    if isinstance(flow.credentials, Credentials):
        credentials = flow.credentials
    else:
        credentials = Credentials(
            token=flow.credentials.token,
            refresh_token=flow.credentials.refresh_token,
            token_uri=flow.credentials.token_uri,
            client_id=flow.credentials.client_id,
            client_secret=flow.credentials.client_secret,
            scopes=flow.credentials.scopes,
        )
    _persist_credentials(get_token_path(), credentials)
    print("Autenticacion completada. Token guardado correctamente.")
    return credentials


def probe_token_state(token_path: Path | None = None) -> str:
    """Classify the current OAuth token state without starting an interactive flow.

    Returns one of the :data:`TOKEN_STATE_*` values. Network problems are reported
    separately so the launcher can start the app in offline/cache mode instead of
    forcing a reauthorization terminal.
    """

    cached_path = token_path or get_token_path()

    if not cached_path.exists():
        return TOKEN_STATE_MISSING

    try:
        credentials = Credentials.from_authorized_user_file(
            str(cached_path),
            scopes=list(SCOPES),
        )
    except (ValueError, json.JSONDecodeError):
        return TOKEN_STATE_NO_REFRESH

    if not credentials.refresh_token:
        return TOKEN_STATE_NO_REFRESH

    if credentials.expired and credentials.token:
        try:
            credentials.refresh(Request())
            _persist_credentials(cached_path, credentials)
        except RefreshError:
            return TOKEN_STATE_REVOKED
        except Exception:
            return TOKEN_STATE_NETWORK

    return TOKEN_STATE_OK


def launcher_exit_code(state: str) -> int:
    """Map a token state to the exit code contract used by the Bash launcher."""

    return _LAUNCHER_EXIT_CODES.get(state, _LAUNCHER_EXIT_CODES[TOKEN_STATE_OK])


def _load_cached_credentials(
    token_path: Path,
    scopes: Sequence[str],
) -> Credentials | None:
    """Load the cached OAuth token if it exists."""

    if not token_path.exists():
        return None

    loaded = Credentials.from_authorized_user_file(
        str(token_path),
        scopes=list(scopes),
    )
    if not isinstance(loaded, Credentials):
        return None
    return loaded


def _persist_credentials(token_path: Path, credentials: Credentials) -> None:
    """Persist OAuth credentials in the local configuration directory.

    The token contains the client secret and refresh token, so it is written
    with owner-only permissions (0600) using an atomic replace.
    """

    token_path.parent.mkdir(parents=True, exist_ok=True)

    if hasattr(credentials, "to_json"):
        payload = credentials.to_json()
    elif hasattr(credentials, "to_authorized_user_info"):
        payload = json.dumps(
            credentials.to_authorized_user_info(),
            ensure_ascii=False,
            indent=2,
        )
    else:
        payload = json.dumps(
            {
                "token": getattr(credentials, "token", None),
                "refresh_token": getattr(credentials, "refresh_token", None),
                "token_uri": getattr(credentials, "token_uri", None),
                "client_id": getattr(credentials, "client_id", None),
                "client_secret": getattr(credentials, "client_secret", None),
                "scopes": list(getattr(credentials, "scopes", []) or []),
            },
            ensure_ascii=False,
            indent=2,
        )

    file_descriptor, temp_name = tempfile.mkstemp(
        dir=token_path.parent,
        prefix=f".{token_path.name}.",
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file_pointer:
            file_pointer.write(payload)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, token_path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
