"""`forge sync`, `ls`, `show` — push skills to consumers and inspect them."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from skill_forge.cli import RootOpt, _die, _resolve_root, app
from skill_forge.storage import filesystem as storage


@app.command()
def sync(
    target: str,
    target_dir: Annotated[
        Path | None,
        typer.Option("--target-dir", help="Override the conventional path for this target."),
    ] = None,
    mode: Annotated[str, typer.Option("--mode", help="symlink | copy")] = "symlink",
    unsync: Annotated[
        bool,
        typer.Option(
            "--unsync",
            help="Remove previously-synced skills instead of placing new ones.",
        ),
    ] = False,
    root: RootOpt = None,
) -> None:
    """Sync promoted skills into a consumer tool's skills directory."""
    from skill_forge.sync import KNOWN_TARGETS, SyncError, sync_target, unsync_target

    base = _resolve_root(root)
    if unsync:
        try:
            removed, expected = unsync_target(base, target=target)
        except SyncError as exc:
            _die(str(exc), 1)
        typer.echo(f"Unsynced: {removed} of {expected} skill(s) removed for target {target!r}")
        return
    try:
        manifest = sync_target(base, target=target, target_dir=target_dir, mode=mode)
    except SyncError as exc:
        typer.echo(str(exc), err=True)
        if target not in KNOWN_TARGETS:
            typer.echo(
                f"  Known targets: {', '.join(sorted(KNOWN_TARGETS))}",
                err=True,
            )
        raise typer.Exit(code=1) from exc
    typer.echo(f"Synced: {len(manifest.entries)} skill(s) → {manifest.target_dir}")
    typer.echo(f"  Mode: {mode}")
    typer.echo(f"  Manifest: sync/{target}.yml")


@app.command(name="ls")
def list_skills(root: RootOpt = None) -> None:
    """List all skills (live + draft) with their scores."""
    base = _resolve_root(root)
    entries = storage.list_skills(base)
    table = Table(title="skills")
    table.add_column("Slug", style="bold")
    table.add_column("Status")
    table.add_column("Score", justify="right")
    for entry in entries:
        score = "—" if entry.judge_score is None else f"{entry.judge_score:.2f}"
        status = "[yellow]draft[/yellow]" if entry.draft else "[green]live[/green]"
        table.add_row(entry.slug, status, score)
    Console().print(table)


@app.command()
def show(slug: str, root: RootOpt = None) -> None:
    """Show SKILL.md content and sources.yml for a slug."""
    base = _resolve_root(root)
    try:
        storage.read_skill(base, slug)
    except FileNotFoundError as exc:
        _die(str(exc), 1)

    live = base / "skills" / slug / "SKILL.md"
    draft = base / "skills" / "_draft" / slug / "SKILL.md"
    path = live if live.is_file() else draft
    status = "draft" if path == draft else "live"

    typer.echo(f"## SKILL.md  ({path}  |  {status})")
    typer.echo("---")
    typer.echo(path.read_text(encoding="utf-8"))
    typer.echo("---")
    typer.echo("")

    sources_path = base / "sources" / f"{slug}.yml"
    typer.echo(f"## sources.yml  ({sources_path})")
    typer.echo("---")
    if sources_path.is_file():
        typer.echo(sources_path.read_text(encoding="utf-8"))
    else:
        typer.echo("[no provenance file]")
    typer.echo("---")
