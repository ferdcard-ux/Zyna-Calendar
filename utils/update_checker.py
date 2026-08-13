"""Check GitHub releases and download/install the packaged app."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GITHUB_API_URL = "https://api.github.com/repos"
DEB_PREFIX = "zyna-calendar_"
DEFAULT_TIMEOUT = 30
HASH_SUFFIX = ".sha256"

logger = logging.getLogger(__name__)


class UpdateCheckError(Exception):
    """Raised when a release cannot be fetched or inspected."""


class UpdateDownloadError(Exception):
    """Raised when an update download fails."""


@dataclass(frozen=True)
class AssetInfo:
    """Metadata for a downloadable release asset."""

    name: str
    url: str
    size: int
    digest_url: str | None = None


@dataclass(frozen=True)
class ReleaseInfo:
    """Summary of the latest GitHub release."""

    tag: str
    version: str
    name: str
    body: str
    html_url: str
    asset: AssetInfo | None


def parse_version(value: str) -> tuple[int, int, int]:
    """Parse ``0.1.7`` or ``v0.1.7`` into a comparable tuple."""

    normalized = value.strip()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    parts = normalized.split("-")[0].split(".")
    numbers: list[int] = []
    for part in parts[:3]:
        if not part.isdigit():
            return (0, 0, 0)
        numbers.append(int(part))
    while len(numbers) < 3:
        numbers.append(0)
    return (numbers[0], numbers[1], numbers[2])


def is_newer_version(candidate: str, current: str) -> bool:
    """Return True when the candidate release is newer than the current version."""

    return parse_version(candidate) > parse_version(current)


def _json_headers() -> dict[str, str]:
    """Return headers that request the GitHub API JSON payload."""

    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": "zyna-calendar",
    }


def fetch_latest_release(repo: str, timeout: float = DEFAULT_TIMEOUT) -> ReleaseInfo:
    """Fetch the latest release for an ``owner/repo`` repository."""

    if "/" not in repo or repo.startswith("/") or repo.endswith("/"):
        raise UpdateCheckError(f"Repositorio no valido: {repo!r}")

    url = f"{GITHUB_API_URL}/{repo}/releases/latest"
    request = Request(url, headers=_json_headers())
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 404:
            raise UpdateCheckError("No se encontro una release estable publicada.") from error
        raise UpdateCheckError(f"GitHub respondio con el codigo {error.code}.") from error
    except URLError as error:
        raise UpdateCheckError(f"No se pudo conectar a GitHub: {error.reason}") from error

    return _build_release_info(payload)


def _build_release_info(payload: dict[str, Any]) -> ReleaseInfo:
    """Turn a GitHub API release payload into a ReleaseInfo instance."""

    tag = str(payload.get("tag_name", ""))
    assets_raw = payload.get("assets", [])
    if not isinstance(assets_raw, list):
        assets_raw = []

    deb_asset: AssetInfo | None = None
    for asset in assets_raw:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name", ""))
        if not name.startswith(DEB_PREFIX) or not name.endswith(".deb"):
            continue
        digest_url = None
        for sibling in assets_raw:
            if not isinstance(sibling, dict):
                continue
            sibling_name = str(sibling.get("name", ""))
            if sibling_name == f"{name}{HASH_SUFFIX}":
                digest_url = str(sibling.get("browser_download_url", ""))
                break
        deb_asset = AssetInfo(
            name=name,
            url=str(asset.get("browser_download_url", "")),
            size=int(asset.get("size") or 0),
            digest_url=digest_url,
        )
        break

    return ReleaseInfo(
        tag=tag,
        version=parse_version_string(tag),
        name=str(payload.get("name") or tag),
        body=str(payload.get("body") or ""),
        html_url=str(payload.get("html_url", "")),
        asset=deb_asset,
    )


def parse_version_string(tag: str) -> str:
    """Return a plain ``X.Y.Z`` version extracted from a release tag."""

    normalized = tag.strip()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    parts = normalized.split("-")[0].split(".")
    digits = [part for part in parts[:3] if part.isdigit()]
    return ".".join(digits) if digits else normalized


def download_asset(
    asset: AssetInfo, destination: Path, progress: Callable[[int, int], None]
) -> None:
    """Download a release asset showing progress via a callback."""

    request = Request(asset.url, headers=_json_headers())
    try:
        with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
            total = int(response.headers.get("Content-Length") or asset.size or 0)
            written = 0
            with destination.open("wb") as file_pointer:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    file_pointer.write(chunk)
                    written += len(chunk)
                    if total > 0:
                        progress(written, total)
    except (HTTPError, URLError) as error:
        destination.unlink(missing_ok=True)
        reason = getattr(error, "reason", None) or getattr(error, "code", str(error))
        raise UpdateDownloadError(f"Fallo la descarga: {reason}") from error


def sha256_of(path: Path, block_size: int = 65536) -> str:
    """Compute the SHA-256 digest of a file as lowercase hex."""

    digest = hashlib.sha256()
    with path.open("rb") as file_pointer:
        while True:
            block = file_pointer.read(block_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def fetch_expected_digest(digest_url: str, timeout: float = DEFAULT_TIMEOUT) -> str | None:
    """Fetch the published ``.sha256`` file and return the lowercase hex digest."""

    try:
        request = Request(digest_url, headers=_json_headers())
        with urlopen(request, timeout=timeout) as response:
            content: str = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError):
        return None
    for token in content.replace("\\t", " ").split():
        candidate = token.replace("*", "").strip()
        if len(candidate) == 64:
            try:
                int(candidate, 16)
            except ValueError:
                continue
            return candidate.lower()
    return None


def verify_digest(path: Path, expected: str) -> bool:
    """Return True when the file digest matches the expected hex value."""

    actual = sha256_of(path)
    return actual.lower() == expected.lower()


def install_deb(path: Path) -> None:
    """Install a downloaded .deb file using a graphical privilege prompt."""

    if not path.exists():
        raise UpdateDownloadError("El paquete descargado no existe.")
    command = ["pkexec", "dpkg", "-i", str(path)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise UpdateDownloadError(f"La instalacion fallo: {detail[:500]}")
