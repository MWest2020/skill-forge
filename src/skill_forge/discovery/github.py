"""GitHub-based candidate discovery via the `gh` CLI."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class GitHubCandidate:
    full_name: str  # e.g. "kubernetes/website"
    html_url: str  # https://github.com/...
    spdx_license: str | None  # SPDX id from GitHub's licenseInfo, or None


class GitHubSearchError(Exception):
    """Wraps gh CLI failures."""


def search_repos(topic: str, *, limit: int = 10) -> list[GitHubCandidate]:
    """Search GitHub repositories for a topic. Returns candidates with license info."""
    try:
        result = subprocess.run(
            [
                "gh",
                "search",
                "repos",
                topic,
                "--limit",
                str(limit),
                "--json",
                "fullName,url,license",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitHubSearchError("`gh` CLI not found; install from https://cli.github.com/") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitHubSearchError("`gh search` timed out after 30s") from exc
    if result.returncode != 0:
        raise GitHubSearchError(
            f"`gh search` exited {result.returncode}: {result.stderr.strip()[:300]}"
        )
    try:
        items = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise GitHubSearchError(f"could not parse `gh search` output: {exc}") from exc
    if not isinstance(items, list):
        raise GitHubSearchError("`gh search` returned non-list payload")

    candidates: list[GitHubCandidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        full_name = str(item.get("fullName", "")).strip()
        html_url = str(item.get("url", "")).strip()
        license_obj = item.get("license") or {}
        spdx = None
        if isinstance(license_obj, dict):
            spdx = (license_obj.get("key") or license_obj.get("spdxId") or "").upper() or None
        if full_name and html_url:
            candidates.append(GitHubCandidate(full_name, html_url, spdx))
    return candidates


__all__ = ["GitHubCandidate", "GitHubSearchError", "search_repos"]
