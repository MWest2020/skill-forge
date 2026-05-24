"""Tests for the `ls` and `show` CLI commands — change #1."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from skill_forge.cli import app
from skill_forge.models import Skill, SourceRef
from skill_forge.storage import filesystem as fs

runner = CliRunner()


def _skill(name: str = "demo-skill", judge_score: float | None = 0.87) -> Skill:
    return Skill(
        name=name,
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        judge_score=judge_score,
        created=date(2026, 5, 24),
        body="# Body\n",
    )


def test_ls_empty(tmp_path: Path) -> None:
    result = runner.invoke(app, ["ls", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "skills" in result.stdout


def test_ls_shows_live_and_drafts(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("live-one", judge_score=0.91), draft=False)
    fs.write_skill(tmp_path, _skill("draft-one", judge_score=None), draft=True)

    result = runner.invoke(app, ["ls", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "live-one" in result.stdout
    assert "draft-one" in result.stdout
    assert "0.91" in result.stdout
    # Score "—" for the draft without judge_score
    assert "—" in result.stdout


def test_show_existing(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)
    result = runner.invoke(app, ["show", "demo-skill", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "SKILL.md" in result.stdout
    assert "demo-skill" in result.stdout
    assert "[no provenance file]" in result.stdout


def test_show_missing_slug(tmp_path: Path) -> None:
    result = runner.invoke(app, ["show", "nope", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "nope" in (result.stderr or result.output)
