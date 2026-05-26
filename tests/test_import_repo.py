"""Tests for forge import-repo — change #10."""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from skill_forge.cli import app
from skill_forge.import_skill import RepoImportError, import_github_repo
from skill_forge.import_skill import repo as repo_mod
from skill_forge.storage import filesystem as fs

runner = CliRunner()

# A valid SKILL.md the importer should accept.
_VALID_SKILL = """\
---
created: '2026-05-26'
description: Use this skill when X.
name: alpha-skill
sources:
- id: src-aaaaaa
version: 1
---

## When to use
Body content.

## Procedure
Steps.

## Failure modes
None.

## Source
- https://example.com
"""


def _ok(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["gh"], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str, code: int = 1) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["gh"], returncode=code, stdout="", stderr=stderr)


def _stub_gh(
    monkeypatch: pytest.MonkeyPatch, responses: dict[str, subprocess.CompletedProcess[str]]
) -> MagicMock:
    """Stub `subprocess.run` so each invocation matches a known endpoint substring."""
    calls: list[list[str]] = []

    def _side_effect(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = args[0] if args else kwargs.get("args", [])
        assert isinstance(argv, list)
        calls.append(argv)
        # Use the first endpoint argument (after `gh api`) for routing
        endpoint = argv[2] if len(argv) > 2 else ""
        for key, response in responses.items():
            if key in endpoint:
                return response
        raise AssertionError(f"unmocked gh call: {argv}")

    mock = MagicMock(side_effect=_side_effect)
    monkeypatch.setattr(repo_mod.subprocess, "run", mock)
    return mock


def _b64(content: str) -> str:
    return base64.b64encode(content.encode("utf-8")).decode("ascii")


# --- URL parsing -------------------------------------------------------------


def test_invalid_github_url_rejected(tmp_path: Path) -> None:
    with pytest.raises(RepoImportError, match="not a GitHub repo URL"):
        import_github_repo(tmp_path, "https://gitlab.com/owner/repo")


def test_strips_git_suffix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_gh(
        monkeypatch,
        {
            # Order matters — more-specific keys first since match uses `in`
            "git/trees/main": _ok(json.dumps({"tree": []})),
            "repos/owner/repo": _ok("main\n"),
        },
    )
    result = import_github_repo(tmp_path, "https://github.com/owner/repo.git")
    assert result.imported == []
    assert result.skipped == []


# --- tree walk + import ------------------------------------------------------


def test_imports_all_skill_md_in_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tree = {
        "tree": [
            {"path": "README.md", "type": "blob"},
            {"path": "skills/alpha/SKILL.md", "type": "blob"},
            {"path": "skills/beta/SKILL.md", "type": "blob"},
            {"path": "skills/notes/random.md", "type": "blob"},
            {"path": "skills", "type": "tree"},  # directory entry — must be skipped
        ]
    }
    beta_content = _VALID_SKILL.replace("alpha-skill", "beta-skill")
    _stub_gh(
        monkeypatch,
        {
            "contents/skills/alpha/SKILL.md": _ok(
                json.dumps({"type": "file", "encoding": "base64", "content": _b64(_VALID_SKILL)})
            ),
            "contents/skills/beta/SKILL.md": _ok(
                json.dumps({"type": "file", "encoding": "base64", "content": _b64(beta_content)})
            ),
            "git/trees/main": _ok(json.dumps(tree)),
            "repos/owner/repo": _ok("main\n"),
        },
    )
    result = import_github_repo(tmp_path, "https://github.com/owner/repo")
    assert sorted(s.name for s in result.imported) == ["alpha-skill", "beta-skill"]
    assert result.skipped == []
    # Source URL was rewritten to the GitHub blob URL
    sources = fs.read_sources(tmp_path, "alpha-skill")
    assert sources.sources[0].url == (
        "https://github.com/owner/repo/blob/main/skills/alpha/SKILL.md"
    )


def test_skips_malformed_skill_md(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tree = {"tree": [{"path": "skills/broken/SKILL.md", "type": "blob"}]}
    _stub_gh(
        monkeypatch,
        {
            "contents/skills/broken/SKILL.md": _ok(
                json.dumps(
                    {"type": "file", "encoding": "base64", "content": _b64("no frontmatter at all")}
                )
            ),
            "git/trees/main": _ok(json.dumps(tree)),
            "repos/owner/repo": _ok("main\n"),
        },
    )
    result = import_github_repo(tmp_path, "https://github.com/owner/repo")
    assert result.imported == []
    assert len(result.skipped) == 1
    assert result.skipped[0][0] == "skills/broken/SKILL.md"


def test_respects_explicit_ref(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = _stub_gh(
        monkeypatch,
        {
            "git/trees/v1.0": _ok(json.dumps({"tree": []})),
        },
    )
    import_github_repo(tmp_path, "https://github.com/owner/repo", ref="v1.0")
    # call.args[0] is the argv list passed to subprocess.run; element 2 is endpoint.
    endpoints = [call.args[0][2] for call in fake.call_args_list]
    assert any("git/trees/v1.0" in e for e in endpoints)
    # No default-branch lookup call (would be exactly "repos/owner/repo")
    assert "repos/owner/repo" not in endpoints


def test_max_skills_cap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tree = {"tree": [{"path": f"skills/s{i}/SKILL.md", "type": "blob"} for i in range(60)]}
    _stub_gh(
        monkeypatch,
        {
            "git/trees/main": _ok(json.dumps(tree)),
            "repos/owner/repo": _ok("main\n"),
        },
    )
    with pytest.raises(RepoImportError, match="max_skills=50"):
        import_github_repo(tmp_path, "https://github.com/owner/repo")


def test_gh_missing_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        repo_mod.subprocess,
        "run",
        MagicMock(side_effect=FileNotFoundError("gh")),
    )
    with pytest.raises(RepoImportError, match="not found"):
        import_github_repo(tmp_path, "https://github.com/owner/repo")


def test_gh_nonzero_exit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_gh(
        monkeypatch,
        {
            "repos/owner/repo": _fail("404 not found", code=1),
        },
    )
    with pytest.raises(RepoImportError, match="exited 1"):
        import_github_repo(tmp_path, "https://github.com/owner/repo")


# --- CLI ---------------------------------------------------------------------


def test_cli_import_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tree = {"tree": [{"path": "skills/alpha/SKILL.md", "type": "blob"}]}
    _stub_gh(
        monkeypatch,
        {
            "contents/skills/alpha/SKILL.md": _ok(
                json.dumps({"type": "file", "encoding": "base64", "content": _b64(_VALID_SKILL)})
            ),
            "git/trees/main": _ok(json.dumps(tree)),
            "repos/owner/repo": _ok("main\n"),
        },
    )
    result = runner.invoke(
        app, ["import-repo", "https://github.com/owner/repo", "--root", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "imported: alpha-skill" in result.output
    assert "1 imported, 0 skipped" in result.output


def test_cli_import_repo_non_github_url(tmp_path: Path) -> None:
    result = runner.invoke(app, ["import-repo", "https://gitlab.com/x/y", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not a GitHub repo URL" in (result.stderr or result.output)
