"""Tests for skill_forge.evaluation.judge — change #2 add-import-and-judge."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from skill_forge.evaluation.judge import judge_skill
from skill_forge.identity import from_seed
from skill_forge.models import (
    JUDGE_AXES,
    JudgeFinding,
    JudgeScore,
    Skill,
    Source,
    SourceRef,
    SourcesFile,
)
from skill_forge.providers.base import DistilledDraft, LLMProvider
from skill_forge.storage import filesystem as fs

_SEED = b"\x33" * 32
_WEIGHTS = {
    "schema_compliance": 0.20,
    "clarity": 0.20,
    "actionability": 0.25,
    "gap_coverage": 0.20,
    "provenance_quality": 0.15,
}


class _FakeJudgeProvider(LLMProvider):
    def __init__(
        self,
        axes: dict[str, float] | None = None,
        findings: list[JudgeFinding] | None = None,
    ) -> None:
        self.axes = axes or {axis: 0.8 for axis in JUDGE_AXES}
        self.findings = findings or []

    def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
        raise NotImplementedError("not used")

    def judge(
        self, skill: Skill, *, weights: dict[str, float]
    ) -> tuple[JudgeScore, list[JudgeFinding]]:
        from skill_forge.providers._judge import build_judge_score

        return build_judge_score(self.axes, weights), self.findings


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
