"""Tests for skill_forge.refinement — change #3 add-refinement-loop."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from skill_forge.identity import from_seed
from skill_forge.lineage import migrate_one
from skill_forge.models import (
    JUDGE_AXES,
    JudgeFinding,
    JudgeScore,
    RunEvent,
    Skill,
    SourceRef,
)
from skill_forge.refinement import (
    NoJudgmentToRefineError,
    PendingIterationExistsError,
    RefinementError,
    accept_iteration,
    refine_skill,
    reject_iteration,
)
from skill_forge.storage import filesystem as fs

from .fakes import FakeProvider

_SEED = b"\x55" * 32


class _RefineProvider(FakeProvider):
    def __init__(self, body: str = "## refined body\n") -> None:
        self.body = body
        self.calls: list[tuple[Skill, list[JudgeFinding], str | None, str | None]] = []

    def refine(
        self,
        skill: Skill,
        *,
        findings: list[JudgeFinding],
        hint: str | None = None,
        extra_source: str | None = None,
    ) -> str:
        self.calls.append((skill, findings, hint, extra_source))
        return self.body


def _skill() -> Skill:
    return Skill(
        name="demo",
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="## When to use\nA\n## Procedure\nB\n## Failure modes\nC\n",
    )


def _seed_judged_skill(tmp_path: Path, findings: list[dict] | None = None) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)
    migrate_one(tmp_path, "demo", draft=False)
    # Append a judged event so refinement has findings to work with.
    if findings is None:
        findings = [{"axis": "clarity", "observation": "too jargony", "severity": "warning"}]
    score_data = {axis: 0.7 for axis in JUDGE_AXES}
    score_data["total"] = 0.7
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    event = RunEvent(
        run_id="run-2026-05-24-001",
        event="judged",
        timestamp=datetime(2026, 5, 24, 14, 0, tzinfo=UTC),
        skill_slug="demo",
        scores=JudgeScore(**score_data),
        findings=[JudgeFinding(**f) for f in findings],
    )
    (runs_dir / "run-2026-05-24-001.jsonl").write_text(
        json.dumps(event.model_dump(mode="json"), separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


# --- refine_skill -------------------------------------------------------------


def test_refine_skill_creates_pending_iteration(tmp_path: Path) -> None:
    _seed_judged_skill(tmp_path)
    provider = _RefineProvider()
    new_version = refine_skill(tmp_path, "demo", provider=provider)
    assert new_version == 2

    # File on disk
    iters = sorted((tmp_path / "skills" / "demo" / "iterations").glob("v2-*.md"))
    assert len(iters) == 1
    assert "## refined body" in iters[0].read_text()

    # Lineage updated
    lineage = fs.read_lineage(tmp_path, "demo", draft=False)
    assert lineage.current_version == 1  # unchanged until accept
    v2 = next(it for it in lineage.iterations if it.version == 2)
    assert v2.status == "pending"
    assert v2.kind == "refined"


def test_refine_skill_appends_audit(tmp_path: Path) -> None:
    _seed_judged_skill(tmp_path)
    refine_skill(tmp_path, "demo", provider=_RefineProvider())
    refined_events = []
    for path in (tmp_path / "runs").glob("*.jsonl"):
        for line in path.read_text().splitlines():
            data = json.loads(line)
            if data.get("event") == "refined":
                refined_events.append(data)
    assert len(refined_events) == 1
    assert refined_events[0]["metadata"]["new_version"] == "2"


def test_refine_passes_findings_and_hint_to_provider(tmp_path: Path) -> None:
    _seed_judged_skill(
        tmp_path,
        findings=[{"axis": "actionability", "observation": "step 3 vague", "severity": "warning"}],
    )
    provider = _RefineProvider()
    refine_skill(tmp_path, "demo", provider=provider, hint="tighten the procedure")
    _, findings, hint, _ = provider.calls[0]
    assert len(findings) == 1
    assert findings[0].axis == "actionability"
    assert hint == "tighten the procedure"


def test_refine_without_judge_raises(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)
    migrate_one(tmp_path, "demo", draft=False)
    with pytest.raises(NoJudgmentToRefineError):
        refine_skill(tmp_path, "demo", provider=_RefineProvider())


def test_refine_pending_exists_raises(tmp_path: Path) -> None:
    _seed_judged_skill(tmp_path)
    refine_skill(tmp_path, "demo", provider=_RefineProvider())  # produces v2 pending
    with pytest.raises(PendingIterationExistsError):
        refine_skill(tmp_path, "demo", provider=_RefineProvider())


def test_refine_without_lineage_raises(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)  # no migrate
    with pytest.raises(RefinementError, match="lineage"):
        refine_skill(tmp_path, "demo", provider=_RefineProvider())


# --- accept_iteration --------------------------------------------------------


def test_accept_iteration_updates_skill_and_lineage(tmp_path: Path) -> None:
    identity = from_seed(tmp_path / "id", _SEED)
    fs.write_skill(tmp_path, _skill(), draft=False, identity=identity)
    migrate_one(tmp_path, "demo", draft=False)
    _seed_audit_with_findings(tmp_path)
    refine_skill(tmp_path, "demo", provider=_RefineProvider("## v2 body\n"), identity=identity)

    accept_iteration(tmp_path, "demo", version=2, identity=identity)

    skill_md = (tmp_path / "skills" / "demo" / "SKILL.md").read_text()
    assert "## v2 body" in skill_md
    lineage = fs.read_lineage(tmp_path, "demo", draft=False)
    assert lineage.current_version == 2
    statuses = {it.version: it.status for it in lineage.iterations}
    assert statuses == {1: "superseded", 2: "current"}


def test_accept_iteration_rejects_non_pending(tmp_path: Path) -> None:
    identity = from_seed(tmp_path / "id", _SEED)
    fs.write_skill(tmp_path, _skill(), draft=False, identity=identity)
    migrate_one(tmp_path, "demo", draft=False)
    with pytest.raises(RefinementError, match="status"):
        accept_iteration(tmp_path, "demo", version=1, identity=identity)


# --- reject_iteration --------------------------------------------------------


def test_reject_iteration_marks_lineage(tmp_path: Path) -> None:
    _seed_judged_skill(tmp_path)
    refine_skill(tmp_path, "demo", provider=_RefineProvider())
    reject_iteration(tmp_path, "demo", version=2, reason="ate the gotcha")
    lineage = fs.read_lineage(tmp_path, "demo", draft=False)
    v2 = next(it for it in lineage.iterations if it.version == 2)
    assert v2.status == "rejected"
    assert v2.reject_reason == "ate the gotcha"
    # File still on disk
    assert any((tmp_path / "skills" / "demo" / "iterations").glob("v2-*.md"))


def test_reject_iteration_requires_reason(tmp_path: Path) -> None:
    _seed_judged_skill(tmp_path)
    refine_skill(tmp_path, "demo", provider=_RefineProvider())
    with pytest.raises(ValueError, match="non-empty reason"):
        reject_iteration(tmp_path, "demo", version=2, reason="  ")


def test_reject_iteration_only_pending(tmp_path: Path) -> None:
    _seed_judged_skill(tmp_path)
    with pytest.raises(RefinementError, match="pending"):
        reject_iteration(tmp_path, "demo", version=1, reason="x")


# --- helpers -----------------------------------------------------------------


def _seed_audit_with_findings(tmp_path: Path) -> None:
    """Append a `judged` event with findings so refine can find them."""
    score_data = {axis: 0.7 for axis in JUDGE_AXES}
    score_data["total"] = 0.7
    event = RunEvent(
        run_id="run-2026-05-24-001",
        event="judged",
        timestamp=datetime(2026, 5, 24, 14, 0, tzinfo=UTC),
        skill_slug="demo",
        scores=JudgeScore(**score_data),
        findings=[JudgeFinding(axis="clarity", observation="vague", severity="warning")],
    )
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "run-2026-05-24-001.jsonl").write_text(
        json.dumps(event.model_dump(mode="json"), separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
