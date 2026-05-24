"""Shared helpers for the judge path — score computation + skill serialization.

Used by both AnthropicProvider.judge and ClaudeCodeProvider.judge.
"""

from __future__ import annotations

from skill_forge.models import JUDGE_AXES, JudgeFinding, JudgeScore, Skill


def compute_total(axes: dict[str, float], weights: dict[str, float]) -> float:
    """Weighted sum of per-axis scores. Both dicts must contain every JUDGE_AXES key."""
    return sum(weights[axis] * axes[axis] for axis in JUDGE_AXES)


def build_judge_score(axes: dict[str, float], weights: dict[str, float]) -> JudgeScore:
    """Construct a validated JudgeScore from per-axis floats + weights."""
    total = compute_total(axes, weights)
    return JudgeScore.model_validate({**axes, "total": total}, context={"weights": weights})


def parse_findings(raw: list[dict[str, str]]) -> list[JudgeFinding]:
    return [JudgeFinding(**item) for item in raw]


def serialize_skill_for_refine(
    skill: Skill,
    findings: list[JudgeFinding],
    hint: str | None,
    extra_source: str | None,
) -> str:
    """Render the skill + findings + optional inputs for the refinement prompt."""
    findings_block = (
        "\n".join(
            f"- [{f.severity}] {f.axis}: {f.observation}" for f in findings
        )
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
