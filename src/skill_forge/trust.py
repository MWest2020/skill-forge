"""Derive a skill's trust tier from verifiable artifacts — read-only.

Gold comes from a verified human attestation; silver from a judged run that
cites a passing same-rubric-version calibration; bronze from clearing the gate.
Nothing here trusts a stored `tier` field — there isn't one.
"""

from __future__ import annotations

from pathlib import Path

from skill_forge.audit import latest_event
from skill_forge.identity import verify_gold
from skill_forge.models import CalibrationRecord, derive_tier
from skill_forge.storage import filesystem as storage


def gold_valid_for(root: Path, slug: str) -> bool:
    """True iff `slug` carries a gold attestation that verifies AND matches the
    live skill's current origin + version (gold lapses on refine)."""
    try:
        sources = storage.read_sources(root, slug)
    except FileNotFoundError:
        return False
    att = sources.gold
    if att is None or not verify_gold(att):
        return False
    try:
        skill = storage.read_skill(root, slug)
    except FileNotFoundError:
        return False
    return att.skill_origin == skill.origin and att.version == skill.version


def compute_tier(
    root: Path,
    slug: str,
    *,
    total_min: float,
    axis_min: float,
    calibration: CalibrationRecord | None = None,
) -> str:
    """The derived tier for `slug` from its latest judged event, gold
    attestation, and (when given) a passing calibration."""
    judged = latest_event(root, slug, "judged")
    return derive_tier(
        judged,
        gold_valid=gold_valid_for(root, slug),
        calibration=calibration,
        total_min=total_min,
        axis_min=axis_min,
    )
