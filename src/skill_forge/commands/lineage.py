"""`forge lineage migrate` — convert flat skills to the iteration-aware layout."""

from __future__ import annotations

from typing import Annotated

import typer

from skill_forge.cli import RootOpt, _resolve_root, lineage_app


@lineage_app.command(name="migrate")
def lineage_migrate(
    slug: Annotated[
        str | None,
        typer.Option("--slug", help="Migrate only this slug (default: all)."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print the plan, write nothing.")
    ] = False,
    root: RootOpt = None,
) -> None:
    """Convert flat skills to the iteration-aware layout (creates lineage.yml + v1)."""
    from skill_forge.lineage import migrate_all, migrate_one

    base = _resolve_root(root)
    if slug is not None:
        for draft in (False, True):
            if migrate_one(base, slug, draft=draft, dry_run=dry_run):
                where = "draft" if draft else "live"
                verb = "would migrate" if dry_run else "migrated"
                typer.echo(f"{verb}: skills/{('_draft/' if draft else '')}{slug} ({where})")
                return
        typer.echo(f"nothing to migrate for {slug!r} (already migrated or not found)")
        return

    migrated = migrate_all(base, dry_run=dry_run)
    if not migrated:
        typer.echo("nothing to migrate (all skills already have lineage.yml)")
        return
    verb = "would migrate" if dry_run else "migrated"
    for s, d in migrated:
        prefix = "skills/_draft" if d else "skills"
        typer.echo(f"{verb}: {prefix}/{s}")
    typer.echo(f"\n{len(migrated)} skill(s) {('would be ' if dry_run else '')}migrated.")
