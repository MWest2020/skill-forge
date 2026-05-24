"""Distill raw content into a draft SKILL.md via the LLM provider (change #2)."""

from __future__ import annotations


def distill(content: str, source_url: str) -> str:
    """Return a draft SKILL.md (frontmatter + body) for the given content."""
    raise NotImplementedError("distiller.distill: implemented in change #2")
