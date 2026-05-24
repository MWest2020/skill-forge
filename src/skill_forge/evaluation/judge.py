"""Orchestrate the judge call: provider → score+findings → audit + sources.yml.

Spec: openspec/changes/add-import-and-judge/specs/judge/spec.md
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.identity import Identity
from skill_forge.models import JudgeFinding, JudgeScore, RunEvent, RunSummary
from skill_forge.providers.base import LLMProvider
from skill_forge.storage import filesystem as storage

MAX_RUN_SUMMARIES_PER_SKILL = 20


def judge_skill(
    root: Path,
    slug: str,
    *,
    provider: LLMProvider,
    weights: dict[str, float],
    identity: Identity | None = None,
) -> tuple[JudgeScore, list[JudgeFinding]]:
    """Score `slug` against the rubric; append RunEvent + RunSummary."""
    skill = storage.read_skill(root, slug, identity=identity)
    score, findings = provider.judge(skill, weights=weights)

    run_id = next_run_id(root)
    append_run_event(
        root,
        RunEvent(
            run_id=run_id,
            event="judged",
            timestamp=datetime.now(UTC),
            skill_slug=slug,
            scores=score,
            promoted=False,
        ),
    )

    _append_run_summary(root, slug, run_id, score.total, promoted=False)
    return score, findings


def _append_run_summary(
    root: Path, slug: str, run_id: str, judge_score: float, *, promoted: bool
) -> None:
    sources = storage.read_sources(root, slug)
    summary = RunSummary(run_id=run_id, judge_score=judge_score, promoted=promoted)
    new_runs = (list(sources.runs) + [summary])[-MAX_RUN_SUMMARIES_PER_SKILL:]
    updated = sources.model_copy(update={"runs": new_runs})
    storage.write_sources(root, slug, updated, overwrite=True)
