"""Tests for `forge calibrate` + calibration persistence — trust-tiers C2 (#4)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skill_forge import cli as cli_mod
from skill_forge.audit import append_run_event, latest_calibration
from skill_forge.cli import app
from skill_forge.identity import from_seed
from skill_forge.models import (
    JUDGE_AXES,
    JudgeProvenance,
    JudgeRun,
    JudgeScore,
    RunEvent,
    Skill,
    Source,
    SourceRef,
    SourcesFile,
)
from skill_forge.storage import filesystem as fs

from .fakes import FakeProvider

runner = CliRunner()
_SEED = b"\x55" * 32
_HEX64 = "a" * 64


class _ScoreByName(FakeProvider):
    """Judge that returns a per-skill score keyed by slug (default 0.9)."""

    def __init__(self, scores: dict[str, float] | None = None) -> None:
        self.scores = scores or {}

    def judge(self, skill: Skill, *, temperature: float = 0.0) -> JudgeRun:
        value = self.scores.get(skill.name, 0.9)
        return JudgeRun(
            axes={a: value for a in JUDGE_AXES},
            findings=[],
            model_id="claude_code:claude",
            prompt_sha256=_HEX64,
        )


def _use_fake(monkeypatch: pytest.MonkeyPatch, scores: dict[str, float] | None = None) -> None:
    monkeypatch.setattr(cli_mod, "ClaudeCodeProvider", lambda **_: _ScoreByName(scores))


def _seed_gold(tmp_path: Path, slug: str) -> None:
    """Create a live, signed, judged skill and gold-attest it."""
    ident = from_seed(tmp_path / "id", _SEED)
    skill = Skill(
        name=slug, description="Use when X.", version=1,
        sources=[SourceRef(id="src-abc123")], created=date(2026, 5, 24), body="# B\n",
    )
    fs.write_skill(tmp_path, skill, draft=False, identity=ident, overwrite=True)
    fs.write_sources(
        tmp_path, slug,
        SourcesFile(slug=slug, sources=[Source(
            id="src-abc123", url="local-author:test", license="unknown",
            fetched_at=datetime(2026, 5, 24, tzinfo=UTC), sha256=_HEX64, contribution="seed",
        )]),
        overwrite=True,
    )
    axes = {a: 0.9 for a in JUDGE_AXES}
    prov = JudgeProvenance(
        provider="x", model_id="x:y", rubric_version="2", prompt_sha256=_HEX64,
        temperature=0.0, runs=1, raw_axes=[axes], median_axes=axes,
    )
    append_run_event(tmp_path, RunEvent(
        run_id="run-2026-06-17-001", event="judged",
        timestamp=datetime(2026, 6, 17, tzinfo=UTC), skill_slug=slug,
        scores=JudgeScore(**axes, total=0.9), judge_provenance=prov,
    ))
    g = runner.invoke(
        app, ["gold", slug, "--root", str(tmp_path), "--gold-home", str(tmp_path / "g")]
    )
    assert g.exit_code == 0, g.output


def _write_weak(tmp_path: Path, slug: str = "weak-sample") -> Path:
    weak_dir = tmp_path / "weak"
    weak_dir.mkdir(parents=True, exist_ok=True)
    (weak_dir / f"{slug}.md").write_text(
        f"---\nname: {slug}\ndescription: Use when X.\nversion: 1\ncreated: '2026-05-24'\n"
        "sources:\n- id: src-abc123\n---\n\n# Weak\n",
        encoding="utf-8",
    )
    return weak_dir


def _set_weak_dir(tmp_path: Path, weak_dir: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "default.yml").write_text(f"calibrate:\n  weak_dir: {weak_dir}\n", encoding="utf-8")


def test_calibrate_aborts_below_min_gold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake(monkeypatch)
    _seed_gold(tmp_path, "a")
    _seed_gold(tmp_path, "b")  # only 2 < default min_gold 3
    result = runner.invoke(app, ["calibrate", "--root", str(tmp_path)])
    assert result.exit_code == 2
    assert "insufficient gold set" in (result.stderr or result.output)
    assert latest_calibration(tmp_path) is None


def test_calibrate_passes_when_grader_agrees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    weak_dir = _write_weak(tmp_path)
    _set_weak_dir(tmp_path, weak_dir)
    # golds score high (default 0.9), the weak sample scores low.
    _use_fake(monkeypatch, {"weak-sample": 0.3})
    for slug in ("a", "b", "c"):
        _seed_gold(tmp_path, slug)
    result = runner.invoke(app, ["calibrate", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output

    record = latest_calibration(tmp_path)
    assert record is not None
    assert record.passed is True
    assert record.agreement == pytest.approx(1.0)
    assert len(record.results) == 4  # 3 golds + 1 weak
    assert all(s.correct for s in record.results)


def test_calibrate_fails_when_grader_drifts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # one gold ("c") is now scored low by the drifted judge → calibration fails.
    _use_fake(monkeypatch, {"c": 0.3})
    for slug in ("a", "b", "c"):
        _seed_gold(tmp_path, slug)
    result = runner.invoke(app, ["calibrate", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output  # a failed calibration is still recorded
    assert "FAIL" in result.output

    record = latest_calibration(tmp_path)
    assert record is not None
    assert record.passed is False
    assert record.agreement == pytest.approx(2 / 3)
    wrong = [s for s in record.results if not s.correct]
    assert [s.slug for s in wrong] == ["c"]


def test_latest_calibration_only_passing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for slug in ("a", "b", "c"):
        _seed_gold(tmp_path, slug)
    # first run fails (c drifts), second run passes.
    _use_fake(monkeypatch, {"c": 0.3})
    runner.invoke(app, ["calibrate", "--root", str(tmp_path)])
    _use_fake(monkeypatch)
    runner.invoke(app, ["calibrate", "--root", str(tmp_path)])

    assert latest_calibration(tmp_path).passed is True  # type: ignore[union-attr]
    assert latest_calibration(tmp_path, passing=True).passed is True  # type: ignore[union-attr]
