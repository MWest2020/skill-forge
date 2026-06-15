"""Tests for skill_forge.evaluation.judge — change #2 add-import-and-judge."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skill_forge.audit import append_run_event, latest_event
from skill_forge.cli import app
from skill_forge.evaluation.judge import judge_skill
from skill_forge.identity import from_seed
from skill_forge.models import (
    JUDGE_AXES,
    JudgeFinding,
    JudgeProvenance,
    JudgeRun,
    RunEvent,
    Skill,
    Source,
    SourceRef,
    SourcesFile,
)
from skill_forge.storage import filesystem as fs

from .fakes import FakeProvider

runner = CliRunner()

_SEED = b"\x33" * 32
_WEIGHTS = {
    "schema_compliance": 0.20,
    "clarity": 0.20,
    "actionability": 0.25,
    "gap_coverage": 0.20,
    "provenance_quality": 0.15,
}


class _FakeJudgeProvider(FakeProvider):
    def __init__(
        self,
        axes: dict[str, float] | None = None,
        findings: list[JudgeFinding] | None = None,
    ) -> None:
        self.axes = axes or {axis: 0.8 for axis in JUDGE_AXES}
        self.findings = findings or []

    def judge(self, skill: Skill, *, temperature: float = 0.0) -> JudgeRun:
        return JudgeRun(
            axes=self.axes, findings=self.findings, model_id="fake:test", prompt_sha256="a" * 64
        )


def _seed_skill_on_disk(tmp_path: Path, slug: str = "demo") -> None:
    skill = Skill(
        name=slug,
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="## When to use\nA\n## Procedure\nB\n## Failure modes\nC\n",
    )
    fs.write_skill(tmp_path, skill, draft=True)
    src = Source(
        id="src-abc123",
        url="local-author:test",
        license="unknown",
        fetched_at=datetime(2026, 5, 24, tzinfo=UTC),
        sha256="a" * 64,
        contribution="seed",
    )
    fs.write_sources(tmp_path, slug, SourcesFile(slug=slug, sources=[src]))


def test_judge_skill_appends_audit_and_run_summary(tmp_path: Path) -> None:
    _seed_skill_on_disk(tmp_path)
    provider = _FakeJudgeProvider()

    score, findings = judge_skill(tmp_path, "demo", provider=provider, weights=_WEIGHTS)

    # Score total matches weighted sum exactly
    expected = sum(_WEIGHTS[a] * 0.8 for a in JUDGE_AXES)
    assert score.total == pytest.approx(expected)
    assert findings == []

    # RunSummary appended to sources.yml
    sources = fs.read_sources(tmp_path, "demo")
    assert len(sources.runs) == 1
    assert sources.runs[0].judge_score == score.total
    assert sources.runs[0].promoted is False

    # RunEvent appended to runs/*.jsonl
    run_files = sorted((tmp_path / "runs").glob("*.jsonl"))
    assert len(run_files) == 1
    event = json.loads(run_files[0].read_text().splitlines()[0])
    assert event["event"] == "judged"
    assert event["skill_slug"] == "demo"
    assert event["scores"]["total"] == score.total


def test_judge_skill_with_identity_verifies_first(tmp_path: Path) -> None:
    identity = from_seed(tmp_path / "id", _SEED)
    skill = Skill(
        name="demo",
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="## When to use\nA\n## Procedure\nB\n## Failure modes\nC\n",
    )
    fs.write_skill(tmp_path, skill, draft=True, identity=identity)
    fs.write_sources(
        tmp_path,
        "demo",
        SourcesFile(
            slug="demo",
            sources=[
                Source(
                    id="src-abc123",
                    url="local-author:test",
                    license="unknown",
                    fetched_at=datetime(2026, 5, 24, tzinfo=UTC),
                    sha256="a" * 64,
                    contribution="seed",
                )
            ],
        ),
    )

    score, _ = judge_skill(
        tmp_path, "demo", provider=_FakeJudgeProvider(), weights=_WEIGHTS, identity=identity
    )
    assert score.total > 0


def test_judge_skill_caps_run_summary_at_20(tmp_path: Path) -> None:
    _seed_skill_on_disk(tmp_path)
    provider = _FakeJudgeProvider()
    for _ in range(25):
        judge_skill(tmp_path, "demo", provider=provider, weights=_WEIGHTS)
    sources = fs.read_sources(tmp_path, "demo")
    assert len(sources.runs) == 20


def test_judge_score_total_equals_weighted_sum() -> None:
    from skill_forge.providers._judge import build_judge_score

    axes = {axis: 0.5 for axis in JUDGE_AXES}
    score = build_judge_score(axes, _WEIGHTS)
    assert score.total == pytest.approx(0.5)


def test_judge_findings_pass_through(tmp_path: Path) -> None:
    _seed_skill_on_disk(tmp_path)
    findings = [
        JudgeFinding(axis="clarity", observation="too jargony", severity="warning"),
        JudgeFinding(axis="actionability", observation="step 3 unclear", severity="info"),
    ]
    provider = _FakeJudgeProvider(findings=findings)
    _, returned = judge_skill(tmp_path, "demo", provider=provider, weights=_WEIGHTS)
    assert returned == findings


class _SeqJudgeProvider(FakeProvider):
    """Returns a different `clarity` per call (others fixed) to exercise median."""

    def __init__(self, clarity_seq: list[float]) -> None:
        self.clarity_seq = clarity_seq
        self.calls = 0

    def judge(self, skill: Skill, *, temperature: float = 0.0) -> JudgeRun:
        axes = {axis: 0.8 for axis in JUDGE_AXES}
        axes["clarity"] = self.clarity_seq[self.calls]
        self.calls += 1
        return JudgeRun(axes=axes, findings=[], model_id="fake:test", prompt_sha256="b" * 64)


def test_judge_skill_medians_across_runs(tmp_path: Path) -> None:
    _seed_skill_on_disk(tmp_path)
    # sorted [0.6, 0.7, 0.9] → lower-median 0.7
    provider = _SeqJudgeProvider([0.6, 0.9, 0.7])
    score, _ = judge_skill(tmp_path, "demo", provider=provider, weights=_WEIGHTS, runs=3)
    assert score.clarity == pytest.approx(0.7)
    assert provider.calls == 3


def test_judge_skill_records_provenance(tmp_path: Path) -> None:
    _seed_skill_on_disk(tmp_path)
    judge_skill(tmp_path, "demo", provider=_SeqJudgeProvider([0.6, 0.9, 0.7]),
                weights=_WEIGHTS, runs=3, temperature=0.0, rubric_version="1")
    event = latest_event(tmp_path, "demo", "judged")
    assert event is not None and event.judge_provenance is not None
    p = event.judge_provenance
    assert p.runs == 3
    assert len(p.raw_axes) == 3
    assert p.prompt_sha256 == "b" * 64
    assert p.rubric_version == "1"
    assert p.median_axes["clarity"] == pytest.approx(0.7)


def test_judge_skill_rejects_zero_runs(tmp_path: Path) -> None:
    _seed_skill_on_disk(tmp_path)
    with pytest.raises(ValueError, match="runs must be >= 1"):
        judge_skill(tmp_path, "demo", provider=_FakeJudgeProvider(), weights=_WEIGHTS, runs=0)


def _write_judged_event(tmp_path: Path, slug: str = "demo") -> None:
    prov = JudgeProvenance(
        provider="fake", model_id="fake:test", rubric_version="1",
        prompt_sha256="c" * 64, temperature=0.0, runs=2,
        raw_axes=[{a: 0.8 for a in JUDGE_AXES}, {a: 0.9 for a in JUDGE_AXES}],
        median_axes={a: 0.8 for a in JUDGE_AXES},
    )
    append_run_event(tmp_path, RunEvent(
        run_id="run-2026-06-15-001", event="judged",
        timestamp=datetime(2026, 6, 15, tzinfo=UTC), skill_slug=slug, judge_provenance=prov,
    ))


def test_cli_judge_explain_prints_provenance(tmp_path: Path) -> None:
    _write_judged_event(tmp_path)
    result = runner.invoke(app, ["judge", "demo", "--explain", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "prompt sha256:  " + "c" * 64 in result.output
    assert "rubric version: 1" in result.output


def test_cli_judge_explain_no_record_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["judge", "nope", "--explain", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "no judged record" in (result.stderr or result.output)
