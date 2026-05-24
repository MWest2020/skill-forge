"""Promote a draft skill to live based on judge score + threshold (change #3)."""

from __future__ import annotations


def promote(slug: str, scores: dict[str, float]) -> bool:
    """Return True if the skill was promoted to live, False if it stays draft."""
    raise NotImplementedError("promoter.promote: implemented in change #3")
