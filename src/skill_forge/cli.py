"""`forge` CLI entrypoint for the skill-forge project."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from skill_forge.storage import filesystem as storage

app = typer.Typer(
    name="forge",
    help="Distill sources into reusable SKILL.md files.",
    no_args_is_help=True,
)

RootOpt = Annotated[
    Path | None,
    typer.Option("--root", help="Project root containing the skills/ tree."),
]


def _resolve_root(root: Path | None) -> Path:
    return root if root is not None else Path.cwd()


@app.command()
def discover(topic: str) -> None:
    """Find candidate sources for a topic and filter by license."""
    raise NotImplementedError("discover: implemented in change #4")


@app.command()
def extract(source_url: str) -> None:
    """Fetch a source and distill it into a draft SKILL.md."""
    raise NotImplementedError("extract: implemented in change #2")


@app.command()
def judge(skill_path: str) -> None:
    """Score an existing SKILL.md against the configured rubric."""
    raise NotImplementedError("judge: implemented in change #3")


@app.command()
def run(topic: str) -> None:
    """Run the full pipeline: discover -> extract -> judge -> promote."""
    raise NotImplementedError("run: implemented in change #4")


@app.command()
def promote(slug: str) -> None:
    """Manually promote a draft skill to live (overrules threshold)."""
    raise NotImplementedError("promote: implemented in change #3")


@app.command()
def demote(slug: str, reason: Annotated[str, typer.Option("--reason", "-r")]) -> None:
    """Manually demote a live skill back to draft, with a reason."""
    raise NotImplementedError("demote: implemented in change #3")


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
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

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


if __name__ == "__main__":
    app()
