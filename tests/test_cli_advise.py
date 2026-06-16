"""Tests for `forge advise` — add-advise-mode."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skill_forge import cli as cli_mod
from skill_forge.cli import app
from skill_forge.models import JUDGE_AXES, JudgeRun, Skill, SourceRef
from skill_forge.storage import filesystem as fs

from .fakes import FakeProvider

runner = CliRunner()


class _FakeJudge(FakeProvider):
    def __init__(self, value: float = 0.85) -> None:
        self.value = value

    def judge(self, skill: Skill, *, temperature: float = 0.0) -> JudgeRun:
        return JudgeRun(
            axes={axis: self.value for axis in JUDGE_AXES},
            findings=[],
            model_id="claude_code:claude",
            prompt_sha256="a" * 64,
        )


def _use_fake(monkeypatch: pytest.MonkeyPatch, value: float = 0.85) -> None:
    monkeypatch.setattr(cli_mod, "ClaudeCodeProvider", lambda **_: _FakeJudge(value))


def _seed(tmp_path: Path, slug: str = "demo") -> None:
    fs.write_skill(
        tmp_path,
        Skill(
            name=slug, description="Use when X.", version=1,
            sources=[SourceRef(id="src-abc123")], created=date(2026, 5, 24), body="# B\n",
        ),
        draft=False,
    )


_VANILLA = "---\nname: raw-skill\ndescription: Use when X.\n---\n\n# Raw\n## When to use\nX.\n"


def test_advise_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake(monkeypatch)
    _seed(tmp_path)
    result = runner.invoke(app, ["advise", "demo", "--runs", "1", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Advice: demo" in result.output
    assert "Verdict: would promote" in result.output


def test_advise_raw_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake(monkeypatch)
    raw = tmp_path / "src" / "SKILL.md"
    raw.parent.mkdir(parents=True)
    raw.write_text(_VANILLA, encoding="utf-8")
    result = runner.invoke(app, ["advise", str(raw), "--runs", "1", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Advice: SKILL.md" in result.output


def test_advise_is_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake(monkeypatch)
    _seed(tmp_path)

    def snapshot() -> dict[str, int]:
        return {str(p): p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}

    before = snapshot()
    runner.invoke(app, ["advise", "demo", "--runs", "1", "--root", str(tmp_path)])
    assert snapshot() == before  # no runs/, no sources rewrite — nothing touched


def test_advise_runs_zero_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake(monkeypatch)
    _seed(tmp_path)
    result = runner.invoke(app, ["advise", "demo", "--runs", "0", "--root", str(tmp_path)])
    assert result.exit_code == 2


def test_advise_not_found_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake(monkeypatch)
    result = runner.invoke(app, ["advise", "nope", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "no skill or file" in (result.stderr or result.output)
