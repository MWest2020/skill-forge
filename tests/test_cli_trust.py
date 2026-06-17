"""Tests for `forge gold` / `forge tier` / ls Tier column — trust-tiers C1."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from typer.testing import CliRunner

from skill_forge.audit import append_calibration, append_run_event
from skill_forge.cli import app
from skill_forge.identity import from_seed
from skill_forge.models import (
    JUDGE_AXES,
    CalibrationRecord,
    CalibrationSample,
    JudgeProvenance,
    JudgeScore,
    RunEvent,
    Skill,
    Source,
    SourceRef,
    SourcesFile,
)
from skill_forge.storage import filesystem as fs

runner = CliRunner()
_SEED = b"\x55" * 32
_HEX64 = "a" * 64


def _gold(tmp_path: Path, slug: str = "demo"):  # type: ignore[no-untyped-def]
    return runner.invoke(
        app, ["gold", slug, "--root", str(tmp_path), "--gold-home", str(tmp_path / "g")]
    )


def _seed_live_judged(tmp_path: Path, slug: str = "demo", *, version: int = 1) -> None:
    ident = from_seed(tmp_path / "id", _SEED)
    skill = Skill(
        name=slug, description="Use when X.", version=version,
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


def test_tier_bronze_before_gold(tmp_path: Path) -> None:
    _seed_live_judged(tmp_path)
    result = runner.invoke(app, ["tier", "demo", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "demo: bronze" in result.output


def test_gold_then_tier_is_gold(tmp_path: Path) -> None:
    _seed_live_judged(tmp_path)
    g = _gold(tmp_path)
    assert g.exit_code == 0, g.output
    t = runner.invoke(app, ["tier", "demo", "--root", str(tmp_path)])
    assert "demo: gold" in t.output


def test_gold_lapses_on_version_bump(tmp_path: Path) -> None:
    _seed_live_judged(tmp_path, version=1)
    _gold(tmp_path)
    # Refine to v2: the attestation (v1) no longer matches → gold lapses.
    _seed_live_judged(tmp_path, version=2)
    t = runner.invoke(app, ["tier", "demo", "--root", str(tmp_path)])
    assert "demo: gold" not in t.output
    assert "demo: bronze" in t.output


def _append_calibration(
    tmp_path: Path, *, rubric: str = "2", when: datetime, passed: bool = True
) -> None:
    append_calibration(tmp_path, CalibrationRecord(
        rubric_version=rubric, model_id="x:y", gold_set_sha256=_HEX64,
        results=[CalibrationSample(
            slug="g", version=1, total=0.9, expected="pass", correct=True,
        )],
        agreement=1.0, passed=passed, calibrated_at=when,
    ))


def test_tier_silver_with_passing_calibration(tmp_path: Path) -> None:
    # judged 2026-06-17 under rubric 2; a passing same-rubric calibration on the
    # next day cites that judge run → silver.
    _seed_live_judged(tmp_path)
    _append_calibration(tmp_path, rubric="2", when=datetime(2026, 6, 18, tzinfo=UTC))
    t = runner.invoke(app, ["tier", "demo", "--root", str(tmp_path)])
    assert t.exit_code == 0, t.output
    assert "demo: silver" in t.output


def test_silver_lapses_on_rubric_bump(tmp_path: Path) -> None:
    # calibration is for rubric 1, but the judge run was rubric 2 → no silver.
    _seed_live_judged(tmp_path)
    _append_calibration(tmp_path, rubric="1", when=datetime(2026, 6, 18, tzinfo=UTC))
    t = runner.invoke(app, ["tier", "demo", "--root", str(tmp_path)])
    assert "demo: silver" not in t.output
    assert "demo: bronze" in t.output


def test_silver_lapses_on_stale_calibration(tmp_path: Path) -> None:
    # calibration predates the judge run → the score wasn't vouched for → bronze.
    _seed_live_judged(tmp_path)
    _append_calibration(tmp_path, rubric="2", when=datetime(2026, 6, 16, tzinfo=UTC))
    t = runner.invoke(app, ["tier", "demo", "--root", str(tmp_path)])
    assert "demo: silver" not in t.output
    assert "demo: bronze" in t.output


def test_failed_calibration_does_not_confer_silver(tmp_path: Path) -> None:
    _seed_live_judged(tmp_path)
    _append_calibration(
        tmp_path, rubric="2", when=datetime(2026, 6, 18, tzinfo=UTC), passed=False
    )
    t = runner.invoke(app, ["tier", "demo", "--root", str(tmp_path)])
    assert "demo: bronze" in t.output


def test_ls_shows_silver(tmp_path: Path) -> None:
    _seed_live_judged(tmp_path)
    _append_calibration(tmp_path, rubric="2", when=datetime(2026, 6, 18, tzinfo=UTC))
    r = runner.invoke(app, ["ls", "--root", str(tmp_path)])
    assert "silver" in r.output


def test_gold_requires_judged(tmp_path: Path) -> None:
    ident = from_seed(tmp_path / "id", _SEED)
    fs.write_skill(
        tmp_path,
        Skill(name="demo", description="Use when X.", version=1,
              sources=[SourceRef(id="src-abc123")], created=date(2026, 5, 24), body="# B\n"),
        draft=False, identity=ident,
    )
    result = _gold(tmp_path)
    assert result.exit_code == 1
    assert "has not been judged" in (result.stderr or result.output)
