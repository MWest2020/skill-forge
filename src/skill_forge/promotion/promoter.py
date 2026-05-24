"""Promote a draft to live (or demote back) with threshold + audit.

Spec: openspec/changes/add-import-and-judge/specs/promote-demote/spec.md
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.identity import Identity
from skill_forge.models import JUDGE_AXES, JudgeScore, RunEvent
from skill_forge.storage import filesystem as storage


class PromotionError(Exception):
    """Base for promote/demote-specific errors."""


class AlreadyPromotedError(PromotionError):
    """Skill is already live, can't promote again."""


class NotLiveError(PromotionError):
    """Demote was called on something that's not currently live."""


class NotJudgedError(PromotionError):
    """Promote was called without a prior judge run (use --force to override)."""


class BelowThresholdError(PromotionError):
    """Promote was called but the latest judge score doesn't meet the threshold."""


class DemoteCollisionError(PromotionError):
    """A draft already exists at the destination — demote would overwrite."""


def promote(
    root: Path,
    slug: str,
    *,
    promotion: dict[str, float],
    force: bool = False,
    identity: Identity | None = None,
) -> Path:
    """Move `skills/_draft/{slug}/` → `skills/{slug}/`. Returns the live path."""
    live_dir = root / "skills" / slug
    draft_dir = root / "skills" / "_draft" / slug
    if not (draft_dir / "SKILL.md").is_file():
        if live_dir.is_dir():
            raise AlreadyPromotedError(f"{slug!r} is already live at {live_dir}")
        raise FileNotFoundError(f"no draft at {draft_dir}")

    # Strict-load (verifies signature when identity is supplied)
    storage.read_skill(root, slug, identity=identity)

    if not force:
        _check_threshold(root, slug, promotion)

    if live_dir.exists():
        raise AlreadyPromotedError(f"{slug!r} already exists at {live_dir}")
    shutil.move(str(draft_dir), str(live_dir))

    append_run_event(
        root,
        RunEvent(
            run_id=next_run_id(root),
            event="promoted",
            timestamp=datetime.now(UTC),
            skill_slug=slug,
            promoted=True,
            metadata={"forced": "true"} if force else {},
        ),
    )
    return live_dir / "SKILL.md"


def demote(
    root: Path,
    slug: str,
    *,
    reason: str,
    identity: Identity | None = None,
) -> Path:
    """Move `skills/{slug}/` → `skills/_draft/{slug}/`. Returns the draft path."""
    if not reason or not reason.strip():
        raise ValueError("demote requires a non-empty reason")
    live_dir = root / "skills" / slug
    draft_dir = root / "skills" / "_draft" / slug
    if not (live_dir / "SKILL.md").is_file():
        raise NotLiveError(f"{slug!r} is not currently live")
    if draft_dir.exists():
        raise DemoteCollisionError(
            f"a draft of {slug!r} already exists at {draft_dir}; "
            "remove or rename it before demoting"
        )

    storage.read_skill(root, slug, identity=identity)

    draft_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(live_dir), str(draft_dir))

    append_run_event(
        root,
        RunEvent(
            run_id=next_run_id(root),
            event="demoted",
            timestamp=datetime.now(UTC),
            skill_slug=slug,
            promoted=False,
            metadata={"reason": reason},
        ),
    )
    return draft_dir / "SKILL.md"


def _check_threshold(root: Path, slug: str, promotion: dict[str, float]) -> None:
    sources = storage.read_sources(root, slug)
    if not sources.runs:
        raise NotJudgedError(
            f"{slug!r} has no judge runs yet; run `forge judge {slug}` "
            "first or pass --force"
        )
    latest = sources.runs[-1]
    total_min = float(promotion.get("total_min", 0.75))
    axis_min = float(promotion.get("axis_min", 0.50))
    if latest.judge_score < total_min:
        raise BelowThresholdError(
            f"latest total {latest.judge_score:.2f} < threshold {total_min:.2f}; "
            "rejudge or pass --force"
        )
    # Per-axis check: RunSummary only carries `total`, but the full JudgeScore
    # is in the JSONL audit. Walk it newest-first to find the matching
    # "judged" event.
    judged = _latest_judge_score(root, slug)
    if judged is not None:
        for axis in JUDGE_AXES:
            value = getattr(judged, axis)
            if value < axis_min:
                raise BelowThresholdError(
                    f"axis {axis} = {value:.2f} < threshold {axis_min:.2f}; "
                    "rejudge or pass --force"
                )


def _latest_judge_score(root: Path, slug: str) -> JudgeScore | None:
    """Walk runs/*.jsonl newest-first; return scores of the latest judged event."""
    runs_dir = root / "runs"
    if not runs_dir.is_dir():
        return None
    for path in sorted(runs_dir.glob("*.jsonl"), reverse=True):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("event") != "judged" or data.get("skill_slug") != slug:
                continue
            scores = data.get("scores")
            if not scores:
                continue
            try:
                return JudgeScore.model_validate(scores)
            except ValidationError:
                continue
    return None
