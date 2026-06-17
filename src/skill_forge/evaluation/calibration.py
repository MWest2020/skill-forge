"""Measure the judge against the human-set gold set.

Calibration re-judges every gold-attested skill (+ optional known-weak
fixtures) under the current rubric and checks the grader still ranks them the
way the humans did: golds `total ≥ total_min`, weak samples below it. A failed
calibration is a valid result — it means the grader drifted.

Spec: openspec/changes/add-trust-tiers-and-calibration/specs/trust-tiers/spec.md
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from skill_forge.evaluation.judge import score_skill
from skill_forge.models import CalibrationRecord, CalibrationSample, Skill
from skill_forge.providers.base import LLMProvider
from skill_forge.storage import filesystem as storage
from skill_forge.trust import gold_valid_for


def collect_gold_set(root: Path) -> list[Skill]:
    """Live skills carrying a valid gold attestation (sorted by slug)."""
    golds: list[Skill] = []
    for entry in storage.list_skills(root):
        if entry.draft or not gold_valid_for(root, entry.slug):
            continue
        golds.append(storage.read_skill(root, entry.slug))
    return golds


def collect_weak_fixtures(weak_dir: Path | None) -> list[Skill]:
    """Parse every `*.md` SKILL fixture under `weak_dir` (sorted), or none."""
    if weak_dir is None or not weak_dir.is_dir():
        return []
    return [storage.read_skill_file(p) for p in sorted(weak_dir.rglob("*.md"))]


def _gold_set_hash(golds: list[Skill]) -> str:
    material = "\n".join(sorted(f"{s.name}:{s.version}" for s in golds))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def calibrate(
    golds: list[Skill],
    weak: list[Skill],
    *,
    provider: LLMProvider,
    weights: dict[str, float],
    total_min: float,
    runs: int = 3,
    temperature: float = 0.0,
    rubric_version: str = "1",
    now: datetime | None = None,
) -> CalibrationRecord:
    """Judge each sample (median-of-N) and build a CalibrationRecord. Expected:
    golds pass the gate, weak samples fail it. No persistence (caller writes)."""
    samples: list[CalibrationSample] = []
    model_id = "unknown"
    for skill, expected in [(g, "pass") for g in golds] + [(w, "fail") for w in weak]:
        score, _, prov = score_skill(
            skill, provider=provider, weights=weights, runs=runs,
            temperature=temperature, rubric_version=rubric_version,
        )
        model_id = prov.model_id
        passes = score.total >= total_min
        correct = passes if expected == "pass" else not passes
        samples.append(CalibrationSample(
            slug=skill.name, version=skill.version, total=score.total,
            expected=expected, correct=correct,
        ))
    correct_n = sum(1 for s in samples if s.correct)
    return CalibrationRecord(
        rubric_version=rubric_version,
        model_id=model_id,
        gold_set_sha256=_gold_set_hash(golds),
        results=samples,
        agreement=correct_n / len(samples) if samples else 0.0,
        passed=all(s.correct for s in samples),
        calibrated_at=now or datetime.now(UTC),
    )
