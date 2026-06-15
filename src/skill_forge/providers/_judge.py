"""Shared helpers for the judge/refine paths — score computation,
skill serialization, and tolerant JSON-out-of-LLM extraction.

Used by all three LLMProvider implementations.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from skill_forge.models import JUDGE_AXES, JudgeFinding, JudgeScore, Skill
from skill_forge.providers.base import LLMProviderError


def compute_total(axes: dict[str, float], weights: dict[str, float]) -> float:
    """Weighted sum of per-axis scores. Both dicts must contain every JUDGE_AXES key."""
    return sum(weights[axis] * axes[axis] for axis in JUDGE_AXES)


def build_judge_score(axes: dict[str, float], weights: dict[str, float]) -> JudgeScore:
    """Construct a validated JudgeScore from per-axis floats + weights."""
    total = compute_total(axes, weights)
    return JudgeScore.model_validate({**axes, "total": total}, context={"weights": weights})


def prompt_sha256(prompt: str) -> str:
    """sha256 of the exact prompt string a provider sends — recorded for audit."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def parse_judge_axes(data: dict[str, Any]) -> tuple[dict[str, float], list[JudgeFinding]]:
    """Pull the 5 per-axis floats + findings from a judge payload (JSON object
    or a tool-use input dict). Shared by all providers so the contract lives once."""
    findings_raw = data.get("findings", [])
    if not isinstance(findings_raw, list):
        raise LLMProviderError("judge payload `findings` must be a list")
    try:
        axes = {axis: float(data[axis]) for axis in JUDGE_AXES}
    except (KeyError, TypeError, ValueError) as exc:
        raise LLMProviderError(f"judge payload missing or non-numeric axis: {exc}") from exc
    return axes, parse_findings(findings_raw)


def parse_findings(raw: list[dict[str, str]]) -> list[JudgeFinding]:
    return [JudgeFinding(**item) for item in raw]


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Parse a JSON object out of LLM stdout. Tolerates fences and prose."""
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def serialize_skill_for_refine(
    skill: Skill,
    findings: list[JudgeFinding],
    hint: str | None,
    extra_source: str | None,
) -> str:
    """Render the skill + findings + optional inputs for the refinement prompt."""
    findings_block = (
        "\n".join(f"- [{f.severity}] {f.axis}: {f.observation}" for f in findings)
        if findings
        else "(no findings — refine to improve overall quality)"
    )
    parts = [
        "## current SKILL.md body",
        skill.body.rstrip("\n"),
        "",
        "## judge findings to address",
        findings_block,
    ]
    if hint:
        parts += ["", "## user hint", hint]
    if extra_source:
        parts += ["", "## additional source material", extra_source]
    return "\n".join(parts)


def serialize_skill_for_judge(skill: Skill) -> str:
    """Render the skill for the judge prompt — frontmatter-as-summary + body.

    We strip signature + origin (irrelevant to scoring) so the judge focuses
    on content. Sources list is shown verbatim so provenance_quality can see
    what it's working with.
    """
    parts = [
        f"# {skill.name}",
        f"description: {skill.description}",
        f"version: {skill.version}",
        f"sources: {[ref.id for ref in skill.sources]}",
        "",
        skill.body.rstrip("\n"),
    ]
    return "\n".join(parts)
