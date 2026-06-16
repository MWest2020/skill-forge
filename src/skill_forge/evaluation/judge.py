"""Orchestrate the judge call: provider → N runs → per-axis median → audit.

Spec: openspec/changes/make-judge-reproducible/specs/judge-provenance/spec.md
(supersedes the single-run judge from add-import-and-judge).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.identity import Identity
from skill_forge.models import (
    JUDGE_AXES,
    JudgeFinding,
    JudgeProvenance,
    JudgeRun,
    JudgeScore,
    RunEvent,
    RunSummary,
    Skill,
)
from skill_forge.providers._judge import build_judge_score, compute_total
from skill_forge.providers.base import LLMProvider
from skill_forge.storage import filesystem as storage

MAX_RUN_SUMMARIES_PER_SKILL = 20


def score_skill(
    skill: Skill,
    *,
    provider: LLMProvider,
    weights: dict[str, float],
    runs: int = 3,
    temperature: float = 0.0,
    rubric_version: str = "1",
) -> tuple[JudgeScore, list[JudgeFinding], JudgeProvenance]:
    """Score a `skill` N times and reduce per axis by median. **No I/O** — pure
    scoring, so it can back both `judge_skill` (which persists) and `advise`
    (which doesn't).

    The per-axis median is variance-bounded, not bit-exact: hosted models drift
    across versions, so the provenance supports *re-checking* from pinned
    inputs, not byte-for-byte replay.
    """
    if runs < 1:
        raise ValueError(f"runs must be >= 1, got {runs}")
    judge_runs = [provider.judge(skill, temperature=temperature) for _ in range(runs)]
    # Same skill + same prompt builder → identical prompt every run. Assert it so
    # a provider that accidentally varies the prompt can't slip a bad record in.
    prompt_hashes = {r.prompt_sha256 for r in judge_runs}
    if len(prompt_hashes) != 1:
        raise ValueError(f"judge prompt drifted across runs: {prompt_hashes}")

    median_axes = {axis: _lower_median([r.axes[axis] for r in judge_runs]) for axis in JUDGE_AXES}
    score = build_judge_score(median_axes, weights)
    findings = _representative_findings(judge_runs, weights)

    first = judge_runs[0]
    provenance = JudgeProvenance(
        provider=first.model_id.split(":", 1)[0],
        model_id=first.model_id,
        rubric_version=rubric_version,
        prompt_sha256=first.prompt_sha256,
        temperature=temperature,
        runs=runs,
        raw_axes=[r.axes for r in judge_runs],
        median_axes=median_axes,
    )
    return score, findings, provenance


def judge_skill(
    root: Path,
    slug: str,
    *,
    provider: LLMProvider,
    weights: dict[str, float],
    identity: Identity | None = None,
    runs: int = 3,
    temperature: float = 0.0,
    rubric_version: str = "1",
) -> tuple[JudgeScore, list[JudgeFinding]]:
    """Read `slug`, score it (median-of-N), and record the score + full
    provenance to the audit trail. Returns the final (median) score + findings."""
    skill = storage.read_skill(root, slug, identity=identity)
    score, findings, provenance = score_skill(
        skill, provider=provider, weights=weights, runs=runs,
        temperature=temperature, rubric_version=rubric_version,
    )
    run_id = next_run_id(root)
    append_run_event(
        root,
        RunEvent(
            run_id=run_id,
            event="judged",
            timestamp=datetime.now(UTC),
            skill_slug=slug,
            scores=score,
            findings=findings,
            promoted=False,
            judge_provenance=provenance,
        ),
    )
    _append_run_summary(root, slug, run_id, score.total, promoted=False)
    return score, findings


def _lower_median(values: list[float]) -> float:
    """Median, taking the lower-middle for even counts — conservative for a gate
    (a borderline score is never nudged up by the reduction)."""
    return sorted(values)[(len(values) - 1) // 2]


def _representative_findings(
    runs: list[JudgeRun], weights: dict[str, float]
) -> list[JudgeFinding]:
    """Findings from the run whose total is the lower-median of the runs — a
    real run's explanation, closest to the score that gates."""
    ordered = sorted(runs, key=lambda r: compute_total(r.axes, weights))
    return ordered[(len(ordered) - 1) // 2].findings


def _append_run_summary(
    root: Path, slug: str, run_id: str, judge_score: float, *, promoted: bool
) -> None:
    sources = storage.read_sources(root, slug)
    summary = RunSummary(run_id=run_id, judge_score=judge_score, promoted=promoted)
    new_runs = (list(sources.runs) + [summary])[-MAX_RUN_SUMMARIES_PER_SKILL:]
    updated = sources.model_copy(update={"runs": new_runs})
    storage.write_sources(root, slug, updated, overwrite=True)
