"""Lineage migration: turn flat skills into the iteration-aware layout.

Spec: openspec/changes/add-refinement-loop/specs/iteration-storage/spec.md
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skill_forge.models import Iteration, Lineage
from skill_forge.storage import filesystem as storage


def migrate_one(root: Path, slug: str, *, draft: bool, dry_run: bool = False) -> bool:
    """Migrate one skill. Returns True if migrated, False if already done or absent."""
    base = root / "skills" / "_draft" / slug if draft else root / "skills" / slug
    skill_md = base / "SKILL.md"
    lineage_yml = base / "lineage.yml"
    if not skill_md.is_file():
        return False
    if lineage_yml.is_file():
        return False  # already migrated
    if dry_run:
        return True

    today = datetime.now(UTC).date()
    # Iterations store body-only — so refine/accept can swap body in/out
    # without ever touching frontmatter. The v1 file must follow the same
    # rule, even though SKILL.md itself includes frontmatter on disk.
    skill = storage.read_skill_file(skill_md)
    storage.write_iteration(
        root, slug,
        body=skill.body, version=1, kind="imported",
        created=today, draft=draft,
    )

    lineage = Lineage(
        slug=slug,
        current_version=1,
        iterations=[
            Iteration(
                version=1,
                kind="imported",
                created=today,
                judge_score=None,
                status="current",
            )
        ],
    )
    storage.write_lineage(root, slug, lineage, draft=draft, overwrite=False)
    return True


def migrate_all(root: Path, *, dry_run: bool = False) -> list[tuple[str, bool]]:
    """Migrate every flat skill. Returns [(slug, draft)] for those migrated."""
    migrated: list[tuple[str, bool]] = []
    for draft, base_dir in [
        (False, root / "skills"),
        (True, root / "skills" / "_draft"),
    ]:
        if not base_dir.is_dir():
            continue
        for child in sorted(base_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if migrate_one(root, child.name, draft=draft, dry_run=dry_run):
                migrated.append((child.name, draft))
    return migrated
