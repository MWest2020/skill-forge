"""Filesystem-backed storage adapter (change #1).

Layout:
    skills/{slug}/SKILL.md          live, promoted skills
    skills/_draft/{slug}/SKILL.md   drafts (below threshold or pending review)
    sources/{slug}.yml              provenance for each skill
    runs/{run_id}.jsonl             per-run audit trail
"""

from __future__ import annotations

from pathlib import Path


def list_skills(root: Path) -> list[str]:
    """Return slugs of all skills (live + draft)."""
    raise NotImplementedError("filesystem.list_skills: implemented in change #1")


def read_skill(root: Path, slug: str) -> str:
    """Return SKILL.md content for a slug (live first, then draft)."""
    raise NotImplementedError("filesystem.read_skill: implemented in change #1")


def read_sources(root: Path, slug: str) -> dict[str, object]:
    """Return parsed sources.yml for a slug."""
    raise NotImplementedError("filesystem.read_sources: implemented in change #1")
