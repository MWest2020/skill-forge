"""LLM-judge that scores a SKILL.md against the rubric (change #3)."""

from __future__ import annotations


def judge(skill_markdown: str) -> dict[str, float]:
    """Return per-axis scores plus a weighted total (0.0 - 1.0)."""
    raise NotImplementedError("judge.judge: implemented in change #3")
