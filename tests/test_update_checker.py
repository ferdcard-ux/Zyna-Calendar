"""Tests for release checking, hashing and asset selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils import update_checker


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.1.7", (0, 1, 7)),
        ("v0.2.0", (0, 2, 0)),
        ("0.1.7-beta", (0, 1, 7)),
        ("2.0", (2, 0, 0)),
        ("garbage", (0, 0, 0)),
    ],
)
def test_parse_version(value: str, expected: tuple[int, int, int]) -> None:
    assert update_checker.parse_version(value) == expected


@pytest.mark.parametrize(
    ("candidate", "current", "expected"),
    [
        ("0.1.8", "0.1.7", True),
        ("0.1.7", "0.1.7", False),
        ("0.2.0", "0.1.9", True),
        ("1.0.0", "0.9.9", True),
        ("0.1.6", "0.1.7", False),
    ],
)
def test_is_newer_version(candidate: str, current: str, expected: bool) -> None:
    assert update_checker.is_newer_version(candidate, current) is expected


def test_parse_version_string_plain() -> None:
    assert update_checker.parse_version_string("v0.1.8") == "0.1.8"
    assert update_checker.parse_version_string("0.1.8-rc1") == "0.1.8"


def test_build_release_info_selects_deb_and_digest() -> None:
    payload = {
        "tag_name": "v0.1.8",
        "name": "Release 0.1.8",
        "body": "notas",
        "html_url": "https://github.com/x/y/releases/tag/v0.1.8",
        "assets": [
            {
                "name": "zyna-calendar_0.1.8_amd64.deb",
                "browser_download_url": "url/deb",
                "size": 100,
            },
            {
                "name": "zyna-calendar_0.1.8_amd64.deb.sha256",
                "browser_download_url": "url/sha",
                "size": 64,
            },
            {"name": "zyna-calendar_0.1.8.tar.gz", "browser_download_url": "url/tar", "size": 200},
        ],
    }

    release = update_checker._build_release_info(payload)

    assert release.version == "0.1.8"
    assert release.asset is not None
    assert release.asset.name == "zyna-calendar_0.1.8_amd64.deb"
    assert release.asset.digest_url == "url/sha"


def test_build_release_info_without_deb() -> None:
    payload = {
        "tag_name": "v0.1.8",
        "name": "Release",
        "body": "",
        "html_url": "",
        "assets": [{"name": "zyna-calendar.tar.gz", "browser_download_url": "url", "size": 10}],
    }

    release = update_checker._build_release_info(payload)

    assert release.asset is None


def test_fetch_latest_release_rejects_invalid_repo() -> None:
    with pytest.raises(update_checker.UpdateCheckError):
        update_checker.fetch_latest_release("invalid")


def test_sha256_of_file(tmp_path: Path) -> None:
    target = tmp_path / "sample.deb"
    target.write_bytes(b"hello world")

    digest = update_checker.sha256_of(target)

    assert digest == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_verify_digest_matches(tmp_path: Path) -> None:
    target = tmp_path / "sample.deb"
    target.write_bytes(b"hello world")
    expected = update_checker.sha256_of(target)

    assert update_checker.verify_digest(target, expected) is True
    assert update_checker.verify_digest(target, "0" * 64) is False


def test_fetch_expected_digest_parses_checksum_file(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9  sample.deb"

    def fake_urlopen(_request: object, *_args: object, **_kwargs: object) -> FakeResponse:
        return FakeResponse()

    monkeypatch.setattr(update_checker, "urlopen", fake_urlopen)

    result = update_checker.fetch_expected_digest("https://example.test/sample.deb.sha256")

    assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
