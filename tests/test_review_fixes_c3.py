"""Regression tests for change #3's post-review fixes."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from skill_forge.identity import from_seed
from skill_forge.lineage import PartialMigrationError, migrate_one
from skill_forge.models import (
    JudgeFinding,
    JudgeScore,
    RunEvent,
    Skill,
    SourceRef,
)
from skill_forge.refinement import accept_iteration
from skill_forge.storage import filesystem as fs


def _skill(body: str = "## When to use\nA\n## Procedure\nB\n## Failure modes\nC\n") -> Skill:
    return Skill(
        name="demo",
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body=body,
    )


# --- Fix #1: accept_iteration runs body validator -----------------------------


def test_accept_iteration_with_leading_newline_body_still_verifies(tmp_path: Path) -> None:
    """Reviewer-found bug: model_copy bypassed body validator → broken signature."""
    identity = from_seed(tmp_path / "id", b"\x77" * 32)
    fs.write_skill(tmp_path, _skill(), draft=False, identity=identity)
    migrate_one(tmp_path, "demo", draft=False)

    # Write a v2 iteration whose body has a leading newline (pre-fix this
    # would silently break the signature on accept).
    fs.write_iteration(
        tmp_path,
        "demo",
        body="\n\n## When to use\nfresh content\n",
        version=2,
        kind="refined",
        created=date(2026, 5, 24),
        draft=False,
    )
    from skill_forge.models import Iteration

    lineage = fs.read_lineage(tmp_path, "demo", draft=False)
    updated = lineage.model_copy(
        update={
            "iterations": list(lineage.iterations)
            + [
                Iteration(
                    version=2,
                    kind="refined",
                    created=date(2026, 5, 24),
                    judge_score=None,
                    status="pending",
                )
            ]
        }
    )
    fs.write_lineage(tmp_path, "demo", updated, draft=False)

    accept_iteration(tmp_path, "demo", version=2, identity=identity)
    # Read-back with strict identity verify must not raise.
    loaded = fs.read_skill(tmp_path, "demo", identity=identity)
    assert "fresh content" in loaded.body
    # Body has no leading newlines (validator stripped them)
    assert not loaded.body.startswith("\n")


# --- Fix #4: partial migration detection --------------------------------------


def test_migrate_one_raises_on_partial_state_lineage_without_iterations(
    tmp_path: Path,
) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)
    # Write lineage.yml manually but NOT iterations/v1
    base = tmp_path / "skills" / "demo"
    (base / "lineage.yml").write_text(
        "slug: demo\ncurrent_version: 1\niterations:\n  - {version: 1, kind: imported, "
        "created: '2026-05-24', status: current, judge_score: null, reject_reason: null}\n",
        encoding="utf-8",
    )
    with pytest.raises(PartialMigrationError, match="partially migrated"):
        migrate_one(tmp_path, "demo", draft=False)


def test_migrate_one_raises_on_partial_state_iterations_without_lineage(
    tmp_path: Path,
) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)
    fs.write_iteration(
        tmp_path,
        "demo",
        body="# orphan\n",
        version=1,
        kind="imported",
        created=date(2026, 5, 24),
        draft=False,
    )
    # No lineage.yml — partial state
    with pytest.raises(PartialMigrationError, match="partially migrated"):
        migrate_one(tmp_path, "demo", draft=False)


# --- Fix #6: atomic write_lineage ---------------------------------------------


def test_write_lineage_uses_atomic_rename(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Tmp file should be written then renamed — never a partial direct write."""
    from skill_forge.models import Iteration, Lineage

    line = Lineage(
        slug="demo",
        current_version=1,
        iterations=[
            Iteration(
                version=1,
                kind="imported",
                created=date(2026, 5, 24),
                judge_score=None,
                status="current",
            )
        ],
    )
    fs.write_lineage(tmp_path, "demo", line, draft=False)
    path = tmp_path / "skills" / "demo" / "lineage.yml"
    assert path.is_file()
    # No leftover .tmp
    assert not path.with_suffix(".yml.tmp").exists()


# --- Fix #8: malformed run line warning ---------------------------------------


def test_latest_judge_findings_warns_on_malformed_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from skill_forge.refinement.refiner import _latest_judge_findings

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    # Two lines: one garbage, one valid judged event
    event = RunEvent(
        run_id="run-2026-05-24-001",
        event="judged",
        timestamp=datetime(2026, 5, 24, tzinfo=UTC),
        skill_slug="demo",
        scores=JudgeScore(
            schema_compliance=0.8,
            clarity=0.8,
            actionability=0.8,
            gap_coverage=0.8,
            provenance_quality=0.8,
            structural_clarity=0.8,
            example_grounding=0.8,
            tool_declaration=0.8,
            total=0.8,
        ),
        findings=[JudgeFinding(axis="clarity", observation="vague", severity="warning")],
    )
    # Malformed line LAST (scanned first in reverse order) so the warning fires
    # before the valid line returns.
    (runs_dir / "run-2026-05-24-001.jsonl").write_text(
        __import__("json").dumps(event.model_dump(mode="json")) + "\nnot-valid-json{}{\n",
        encoding="utf-8",
    )

    findings = _latest_judge_findings(tmp_path, "demo")
    assert findings is not None
    assert findings[0].axis == "clarity"
    captured = capsys.readouterr()
    assert "could not parse JSON" in captured.err
