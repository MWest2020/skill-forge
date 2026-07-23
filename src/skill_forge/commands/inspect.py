"""`forge sync`, `ls`, `show` — push skills to consumers and inspect them."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from skill_forge.audit import latest_calibration
from skill_forge.cli import RootOpt, _die, _resolve_root, app
from skill_forge.config import load as load_config
from skill_forge.storage import filesystem as storage
from skill_forge.trust import compute_tier


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
    tag: Annotated[
        str | None,
        typer.Option("--tag", help="Limit to the skillset carrying this tag."),
    ] = None,
    root: RootOpt = None,
) -> None:
    """Sync promoted skills into a consumer tool's skills directory."""
    from skill_forge.sync import KNOWN_TARGETS, SyncError, sync_target, unsync_target

    base = _resolve_root(root)
    if unsync:
        try:
            removed, expected = unsync_target(base, target=target, tag=tag)
        except SyncError as exc:
            _die(str(exc), 1)
        typer.echo(f"Unsynced: {removed} of {expected} skill(s) removed for target {target!r}")
        return
    try:
        manifest, placed = sync_target(
            base, target=target, target_dir=target_dir, mode=mode, tag=tag
        )
    except SyncError as exc:
        typer.echo(str(exc), err=True)
        if target not in KNOWN_TARGETS:
            typer.echo(
                f"  Known targets: {', '.join(sorted(KNOWN_TARGETS))}",
                err=True,
            )
        raise typer.Exit(code=1) from exc
    total = len(manifest.entries)
    headline = f"Synced: {placed} skill(s) → {manifest.target_dir}"
    if placed != total:
        headline += f"  (target now holds {total} across all skillsets)"
    typer.echo(headline)
    typer.echo(f"  Mode: {mode}")
    typer.echo(f"  Manifest: sync/{target}.yml")


@app.command(name="ls")
def list_skills(
    root: RootOpt = None,
    tag: Annotated[
        str | None, typer.Option("--tag", help="Only skills carrying this tag.")
    ] = None,
) -> None:
    """List all skills (live + draft) with their scores."""
    base = _resolve_root(root)
    entries = storage.list_skills(base)
    if tag is not None:
        entries = [e for e in entries if tag in e.tags]
    promotion = load_config(base)["promotion"]
    total_min = float(promotion.get("total_min", 0.75))
    axis_min = float(promotion.get("axis_min", 0.50))
    table = Table(title="skills" if tag is None else f"skills tagged {tag!r}")
    table.add_column("Slug", style="bold")
    table.add_column("Status")
    table.add_column("Score", justify="right")
    table.add_column("Tier")
    table.add_column("Tags")
    calibration = latest_calibration(base, passing=True)
    for entry in entries:
        score = "—" if entry.judge_score is None else f"{entry.judge_score:.2f}"
        status = "[yellow]draft[/yellow]" if entry.draft else "[green]live[/green]"
        tier = compute_tier(
            base, entry.slug, total_min=total_min, axis_min=axis_min, calibration=calibration
        )
        table.add_row(entry.slug, status, score, tier, ", ".join(entry.tags))
    Console().print(table)


@app.command()
def tags(root: RootOpt = None) -> None:
    """List tags present on live skills with their skill counts."""
    base = _resolve_root(root)
    counts: dict[str, int] = {}
    for entry in storage.list_skills(base):
        if entry.draft:
            continue
        for t in entry.tags:
            counts[t] = counts.get(t, 0) + 1
    if not counts:
        typer.echo("No tags on live skills.")
        return
    width = max(len(t) for t in counts)
    for t in sorted(counts):
        typer.echo(f"{t:<{width}} {counts[t]}")


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
