"""Tests for skill_forge.promotion.promoter — change #2 add-import-and-judge."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from skill_forge.models import (
    RunSummary,
    Skill,
    Source,
    SourceRef,
    SourcesFile,
)
from skill_forge.promotion.promoter import (
    AlreadyPromotedError,
    BelowThresholdError,
    DemoteCollisionError,
    NotJudgedError,
    NotLiveError,
    demote,
    promote,
)
from skill_forge.storage import filesystem as fs

_PROMOTION = {"total_min": 0.75, "axis_min": 0.50}


def _seed_draft(tmp_path: Path, slug: str = "demo", judge_score: float | None = None) -> None:
    skill = Skill(
        name=slug,
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="## When to use\nA\n## Procedure\nB\n## Failure modes\nC\n",
    )
    fs.write_skill(tmp_path, skill, draft=True)
    runs = (
        [RunSummary(run_id="run-2026-05-24-001", judge_score=judge_score, promoted=False)]
        if judge_score is not None
        else []
    )
    fs.write_sources(
        tmp_path,
        slug,
        SourcesFile(
            slug=slug,
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
            runs=runs,
        ),
    )


# --- promote ------------------------------------------------------------------


def test_promote_succeeds_at_threshold(tmp_path: Path) -> None:
    _seed_draft(tmp_path, judge_score=0.80)
    path = promote(tmp_path, "demo", promotion=_PROMOTION)
    assert path == tmp_path / "skills" / "demo" / "SKILL.md"
    assert path.is_file()
    assert not (tmp_path / "skills" / "_draft" / "demo").exists()


def test_promote_below_threshold_raises(tmp_path: Path) -> None:
    _seed_draft(tmp_path, judge_score=0.50)
    with pytest.raises(BelowThresholdError):
        promote(tmp_path, "demo", promotion=_PROMOTION)
    # Draft still there
    assert (tmp_path / "skills" / "_draft" / "demo" / "SKILL.md").is_file()


def test_promote_force_overrides_threshold(tmp_path: Path) -> None:
    _seed_draft(tmp_path, judge_score=0.10)
    path = promote(tmp_path, "demo", promotion=_PROMOTION, force=True)
    assert path.is_file()


def test_promote_axis_min_check_blocks_skewed_score(tmp_path: Path) -> None:
    """Total >= total_min but one axis < axis_min → BelowThresholdError."""
    _seed_draft(tmp_path, judge_score=0.85)  # total above threshold
    # Append a "judged" event with one axis at 0.30 (below axis_min 0.50)
    skewed_scores = {
        "schema_compliance": 0.95,
        "clarity": 0.95,
        "actionability": 0.95,
        "gap_coverage": 0.95,
        "provenance_quality": 0.30,
        "total": 0.85,
    }
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "run-2026-05-24-001.jsonl").write_text(
        json.dumps(
            {
                "run_id": "run-2026-05-24-001",
                "event": "judged",
                "timestamp": "2026-05-24T14:00:00+00:00",
                "skill_slug": "demo",
                "scores": skewed_scores,
                "promoted": False,
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(BelowThresholdError, match="provenance_quality"):
        promote(tmp_path, "demo", promotion=_PROMOTION)


def test_promote_unjudged_raises_unless_forced(tmp_path: Path) -> None:
    _seed_draft(tmp_path)  # no runs
    with pytest.raises(NotJudgedError):
        promote(tmp_path, "demo", promotion=_PROMOTION)
    # Force overrides
    path = promote(tmp_path, "demo", promotion=_PROMOTION, force=True)
    assert path.is_file()


def test_promote_writes_audit_event(tmp_path: Path) -> None:
    _seed_draft(tmp_path, judge_score=0.80)
    promote(tmp_path, "demo", promotion=_PROMOTION)
    run_files = sorted((tmp_path / "runs").glob("*.jsonl"))
    assert len(run_files) >= 1
    # Search across all run files for a promoted event for this slug.
    found = False
    for path in run_files:
        for line in path.read_text().splitlines():
            event = json.loads(line)
            if event["event"] == "promoted" and event["skill_slug"] == "demo":
                assert event["promoted"] is True
                found = True
    assert found


def test_promote_already_live(tmp_path: Path) -> None:
    _seed_draft(tmp_path, judge_score=0.80)
    promote(tmp_path, "demo", promotion=_PROMOTION)
    # Try again
    with pytest.raises(AlreadyPromotedError):
        promote(tmp_path, "demo", promotion=_PROMOTION)


def test_promote_missing_draft(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        promote(tmp_path, "ghost", promotion=_PROMOTION)


# --- demote -------------------------------------------------------------------


def test_demote_round_trip(tmp_path: Path) -> None:
    _seed_draft(tmp_path, judge_score=0.80)
    promote(tmp_path, "demo", promotion=_PROMOTION)
    path = demote(tmp_path, "demo", reason="regression discovered")
    assert path == tmp_path / "skills" / "_draft" / "demo" / "SKILL.md"
    assert path.is_file()
    assert not (tmp_path / "skills" / "demo").exists()


def test_demote_not_live(tmp_path: Path) -> None:
    _seed_draft(tmp_path)
    with pytest.raises(NotLiveError):
        demote(tmp_path, "demo", reason="x")


def test_demote_collision(tmp_path: Path) -> None:
    _seed_draft(tmp_path, judge_score=0.80)
    promote(tmp_path, "demo", promotion=_PROMOTION)
    # Recreate a draft to collide with demote target
    (tmp_path / "skills" / "_draft" / "demo").mkdir(parents=True)
    (tmp_path / "skills" / "_draft" / "demo" / "SKILL.md").write_text("---\n---\n")
    with pytest.raises(DemoteCollisionError):
        demote(tmp_path, "demo", reason="x")


def test_demote_requires_non_empty_reason(tmp_path: Path) -> None:
    _seed_draft(tmp_path, judge_score=0.80)
    promote(tmp_path, "demo", promotion=_PROMOTION)
    with pytest.raises(ValueError, match="non-empty reason"):
        demote(tmp_path, "demo", reason="   ")


def test_demote_writes_audit_with_reason(tmp_path: Path) -> None:
    _seed_draft(tmp_path, judge_score=0.80)
    promote(tmp_path, "demo", promotion=_PROMOTION)
    demote(tmp_path, "demo", reason="outdated steps")
    # promote and demote each get their own run_id → two files
    run_files = sorted((tmp_path / "runs").glob("*.jsonl"))
    demote_event = json.loads(run_files[-1].read_text().splitlines()[-1])
    assert demote_event["event"] == "demoted"
    assert demote_event["metadata"]["reason"] == "outdated steps"
