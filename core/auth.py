"""OAuth2 authentication helpers for Google Calendar."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from utils.config import get_credentials_path, get_token_path

SCOPES = ("https://www.googleapis.com/auth/calendar.readonly",)


class MissingCredentialsError(FileNotFoundError):
    """Raised when the OAuth client credentials file is not available."""


def load_google_credentials(
    scopes: Sequence[str] | None = None,
    force_reauth: bool = False,
) -> Credentials:
    """Load Google credentials, refreshing or reauthorizing when needed."""

    requested_scopes = list(scopes or SCOPES)
    token_path = get_token_path()
    credentials_path = get_credentials_path()

    credentials = None if force_reauth else _load_cached_credentials(token_path, requested_scopes)

    # 1. Intentar refrescar si es posible
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            _persist_credentials(token_path, credentials)
            return credentials
        except RefreshError:
            print("No se pudo refrescar el token. Se solicitara una nueva autorizacion.")
            credentials = None
        except Exception:
            print("No se pudo refrescar el token por un error inesperado. Se solicitara una nueva autorizacion.")
            credentials = None

    # 2. Si no hay credenciales válidas, iniciar flujo manual OOB
    if not credentials or not credentials.valid:
        if not credentials_path.exists():
            raise MissingCredentialsError(f"Falta credentials.json en {credentials_path}")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path),
            requested_scopes,
        )
        flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
        )

        print(f"\n{'='*60}\nAUTORIZACIÓN REQUERIDA\n1. Abre: {auth_url}\n2. Pega el código abajo\n{'='*60}")
        code = input("Código: ").strip()

        try:
            flow.fetch_token(code=code)
        except Exception as error:
            print("Autenticacion fallida. El codigo es invalido o expirado.")
            raise error

        credentials = flow.credentials
        _persist_credentials(token_path, credentials)
        print("Autenticacion completada. Token guardado correctamente.")

    return credentials


def _load_cached_credentials(
    token_path: Path,
    scopes: Sequence[str],
) -> Credentials | None:
    """Load the cached OAuth token if it exists."""

    if not token_path.exists():
        return None

    return Credentials.from_authorized_user_file(
        str(token_path),
        scopes=list(scopes),
    )


def _persist_credentials(token_path: Path, credentials: Credentials) -> None:
    """Persist OAuth credentials in the local configuration directory."""

    token_path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(credentials, "to_json"):
        token_path.write_text(credentials.to_json(), encoding="utf-8")
        return

    if hasattr(credentials, "to_authorized_user_info"):
        payload = credentials.to_authorized_user_info()
    else:
        payload = {
            "token": getattr(credentials, "token", None),
            "refresh_token": getattr(credentials, "refresh_token", None),
            "token_uri": getattr(credentials, "token_uri", None),
            "client_id": getattr(credentials, "client_id", None),
            "client_secret": getattr(credentials, "client_secret", None),
            "scopes": list(getattr(credentials, "scopes", []) or []),
        }

    token_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
