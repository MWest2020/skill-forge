"""Core domain models: Skill, Source, Run, JudgeScore.

Placeholder signatures — full implementation lands in change #1
(add-core-models-and-storage).
"""

from __future__ import annotations


class Skill:
    """A reusable SKILL.md document with frontmatter and body."""


class Source:
    """A bron (URL / repo / file) used to extract one or more skills."""


class Run:
    """One pipeline run: discovery -> extraction -> judge -> promote."""


class JudgeScore:
    """LLM-judge score for a skill, broken down per rubric axis."""
