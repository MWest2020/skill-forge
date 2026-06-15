"""Tests for `forge identity show` and `forge identity backfill`."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skill_forge.cli import app
from skill_forge.identity import from_seed
from skill_forge.models import Skill, SourceRef
from skill_forge.storage import filesystem as fs

runner = CliRunner()
_SEED = b"\x42" * 32


def _skill(name: str = "demo-skill", origin: str | None = None) -> Skill:
    return Skill(
        name=name,
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="# Body\n",
        origin=origin,
    )


# --- forge identity show ------------------------------------------------------


def test_identity_show_generates_and_prints(tmp_path: Path) -> None:
    result = runner.invoke(app, ["identity", "show", "--home", str(tmp_path)])
    assert result.exit_code == 0
    assert "Generated new identity" in result.output
    assert "Instance ID: forge-" in result.output
    assert "BEGIN PUBLIC KEY" in result.output
    assert "back this file up" in result.output


def test_identity_show_second_call_omits_banner(tmp_path: Path) -> None:
    runner.invoke(app, ["identity", "show", "--home", str(tmp_path)])
    result = runner.invoke(app, ["identity", "show", "--home", str(tmp_path)])
    assert result.exit_code == 0
    assert "Generated new identity" not in result.output
    assert "Instance ID: forge-" in result.output


# --- --home threads through main commands (maintainability #3) ----------------


def test_import_honors_home_override(tmp_path: Path) -> None:
    """A main command (not just `identity`) must sign with the identity at
    --home, proving the override is threaded through rather than hardcoded."""
    root = tmp_path / "repo"
    root.mkdir()
    custom_home = tmp_path / "custom-id"
    src = tmp_path / "src"
    src.mkdir()
    (src / "SKILL.md").write_text(
        "---\n"
        "name: home-probe\n"
        "description: Use when X.\n"
        "version: 1\n"
        "created: '2026-05-24'\n"
        "sources:\n"
        "- id: src-abc123\n"
        "---\n"
        "# Body\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["import", str(src / "SKILL.md"), "--home", str(custom_home), "--root", str(root)],
    )

    assert result.exit_code == 0, result.output
    # The keypair landed in the overridden home, not the default location.
    assert custom_home.is_dir() and any(custom_home.iterdir())


# --- forge identity backfill --------------------------------------------------


def _write_unsigned_skill(root: Path, name: str = "demo-skill", *, draft: bool = True) -> Path:
    return fs.write_skill(root, _skill(name=name), draft=draft)


def test_backfill_stamps_missing_fields(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    home = tmp_path / "home"
    _write_unsigned_skill(root)

    result = runner.invoke(app, ["identity", "backfill", "--root", str(root), "--home", str(home)])
    assert result.exit_code == 0
    assert "stamped:" in result.output

    identity = from_seed(home / "verify", _SEED)  # any identity to load+verify shape
    # Load via the actual identity from `home` (the one backfill used):
    from skill_forge.identity import get_or_create

    real_identity = get_or_create(home)
    loaded = fs.read_skill(root, "demo-skill", identity=real_identity)
    assert loaded.origin == f"{real_identity.instance_id}:demo-skill:1"
    assert loaded.signature is not None
    # Ensure the identity helper variable was just for the lint check, not used:
    del identity


def test_backfill_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    home = tmp_path / "home"
    _write_unsigned_skill(root)

    runner.invoke(app, ["identity", "backfill", "--root", str(root), "--home", str(home)])
    second = runner.invoke(app, ["identity", "backfill", "--root", str(root), "--home", str(home)])
    assert second.exit_code == 0
    assert "stamped:" not in second.output
    assert "already signed" in second.output


def test_backfill_skips_foreign_origin(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    home = tmp_path / "home"
    foreign_identity = from_seed(tmp_path / "foreign", _SEED)
    # Write a skill signed by a foreign identity
    fs.write_skill(
        root,
        _skill().model_copy(update={"origin": f"{foreign_identity.instance_id}:demo-skill:1"}),
        draft=True,
        identity=foreign_identity,
    )

    result = runner.invoke(app, ["identity", "backfill", "--root", str(root), "--home", str(home)])
    assert result.exit_code == 0
    assert "foreign origin" in result.output

    # Foreign signature is preserved.
    loaded = fs.read_skill(root, "demo-skill")
    assert loaded.origin is not None
    assert loaded.origin.startswith(foreign_identity.instance_id)


def test_backfill_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    home = tmp_path / "home"
    path = _write_unsigned_skill(root)
    original_bytes = path.read_bytes()

    result = runner.invoke(
        app,
        [
            "identity",
            "backfill",
            "--root",
            str(root),
            "--home",
            str(home),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "would stamp:" in result.output
    assert path.read_bytes() == original_bytes


def test_extract_threads_identity_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: forge extract stamps the produced draft with our identity."""
    fixture = tmp_path / "src.html"
    fixture.write_text("<html><body>hi</body></html>", encoding="utf-8")
    root = tmp_path / "repo"
    home = tmp_path / "home"
    (root / "config").mkdir(parents=True)
    (root / "config" / "default.yml").write_text(
        "providers:\n  extract: claude_code\n", encoding="utf-8"
    )

    # Patch the ClaudeCodeProvider as imported into the CLI module.
    from skill_forge import cli as cli_mod
    from skill_forge.providers.base import DistilledDraft

    from .fakes import FakeProvider

    class _Fake(FakeProvider):
        def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
            return DistilledDraft(
                name="smoke-stamp",
                description="Use this skill when X.",
                body="## When to use\n...\n## Procedure\n...\n## Failure modes\n...\n",
            )

    monkeypatch.setattr(cli_mod, "ClaudeCodeProvider", lambda **_: _Fake())
    monkeypatch.setenv("SKILL_FORGE_HOME", str(home))

    result = runner.invoke(app, ["extract", f"file://{fixture}", "--root", str(root)])
    assert result.exit_code == 0, result.output

    from skill_forge.identity import get_or_create

    identity = get_or_create(home)
    loaded = fs.read_skill(root, "smoke-stamp", identity=identity)
    assert loaded.origin == f"{identity.instance_id}:smoke-stamp:1"
    assert loaded.signature is not None
