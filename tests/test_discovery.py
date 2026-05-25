"""Tests for skill_forge.discovery — change #4."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from skill_forge.cli import app
from skill_forge.discovery import github as gh_mod
from skill_forge.discovery.github import (
    GitHubCandidate,
    GitHubSearchError,
    search_repos,
)
from skill_forge.discovery.license_check import classify_html, classify_spdx

runner = CliRunner()


def _ok(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["gh"], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["gh"], returncode=1, stdout="", stderr=stderr)


# --- search_repos ------------------------------------------------------------


def test_search_repos_parses_gh_output(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps([
        {"fullName": "kubernetes/website", "url": "https://github.com/kubernetes/website",
         "license": {"key": "apache-2.0", "spdxId": "Apache-2.0"}},
        {"fullName": "some/repo", "url": "https://github.com/some/repo",
         "license": {"key": "mit", "spdxId": "MIT"}},
    ])
    monkeypatch.setattr(gh_mod.subprocess, "run", MagicMock(return_value=_ok(payload)))
    candidates = search_repos("kubernetes", limit=5)
    assert len(candidates) == 2
    assert candidates[0] == GitHubCandidate(
        "kubernetes/website", "https://github.com/kubernetes/website", "APACHE-2.0"
    )


def test_search_repos_missing_gh_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gh_mod.subprocess, "run",
        MagicMock(side_effect=FileNotFoundError("gh")),
    )
    with pytest.raises(GitHubSearchError, match="not found"):
        search_repos("anything")


def test_search_repos_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gh_mod.subprocess, "run", MagicMock(return_value=_fail("auth required"))
    )
    with pytest.raises(GitHubSearchError, match="exited 1"):
        search_repos("anything")


def test_search_repos_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gh_mod.subprocess, "run",
        MagicMock(side_effect=subprocess.TimeoutExpired("gh", 30)),
    )
    with pytest.raises(GitHubSearchError, match="timed out"):
        search_repos("anything")


def test_search_repos_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gh_mod.subprocess, "run", MagicMock(return_value=_ok("garbage")))
    with pytest.raises(GitHubSearchError, match="parse"):
        search_repos("anything")


def test_search_repos_no_license_field(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps([
        {"fullName": "a/b", "url": "https://github.com/a/b", "license": None},
    ])
    monkeypatch.setattr(gh_mod.subprocess, "run", MagicMock(return_value=_ok(payload)))
    candidates = search_repos("topic")
    assert candidates[0].spdx_license is None


# --- classify_spdx -----------------------------------------------------------


@pytest.mark.parametrize(
    "spdx,bucket",
    [
        ("MIT", "permissive"),
        ("Apache-2.0", "permissive"),
        ("BSD-3-Clause", "permissive"),
        ("UNLICENSE", "permissive"),
        ("GPL-3.0", "copyleft"),
        ("AGPL-3.0", "copyleft"),
        ("EUPL-1.2", "copyleft"),
        ("CC-BY-NC-4.0", "restrictive"),
        ("BUSL-1.1", "restrictive"),
        ("OTHER", "forbidden"),
        (None, "forbidden"),
        ("unknown-license", "forbidden"),
    ],
)
def test_classify_spdx_buckets(spdx: str | None, bucket: str) -> None:
    assert classify_spdx(spdx) == bucket


# --- classify_html -----------------------------------------------------------


def test_classify_html_finds_spdx_in_body() -> None:
    body = '<html>Licensed under <a rel="license">Apache-2.0</a></html>'
    assert classify_html(body) == "permissive"


def test_classify_html_no_hints_returns_forbidden() -> None:
    assert classify_html("<html>nothing relevant here</html>") == "forbidden"


def test_classify_html_empty_body() -> None:
    assert classify_html("") == "forbidden"


# --- CLI ---------------------------------------------------------------------


def test_cli_discover_prints_table(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = json.dumps([
        {"fullName": "good/permissive", "url": "https://github.com/good/permissive",
         "license": {"key": "mit", "spdxId": "MIT"}},
        {"fullName": "bad/unknown", "url": "https://github.com/bad/unknown",
         "license": None},
    ])
    monkeypatch.setattr(gh_mod.subprocess, "run", MagicMock(return_value=_ok(payload)))
    result = runner.invoke(app, ["discover", "kubernetes", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "good/permissive" in result.output
    assert "bad/unknown" not in result.output  # filtered out
    assert "1/2 kept" in result.output
    blocked_lines = (tmp_path / "discovery_blocked.log").read_text().splitlines()
    assert len(blocked_lines) == 1
    blocked_entry = json.loads(blocked_lines[0])
    assert blocked_entry["url"] == "https://github.com/bad/unknown"
    assert blocked_entry["reason"] == "none"


def test_cli_discover_gh_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        gh_mod.subprocess, "run",
        MagicMock(side_effect=FileNotFoundError("gh")),
    )
    result = runner.invoke(app, ["discover", "x", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not found" in (result.stderr or result.output)
