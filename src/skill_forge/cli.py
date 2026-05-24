"""skill-forge CLI entrypoint."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="skill-forge",
    help="Distill sources into reusable SKILL.md files.",
    no_args_is_help=True,
)


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
def demote(slug: str, reason: str = typer.Option(..., "--reason", "-r")) -> None:
    """Manually demote a live skill back to draft, with a reason."""
    raise NotImplementedError("demote: implemented in change #3")


@app.command(name="ls")
def list_skills() -> None:
    """List all skills (live + draft) with their scores."""
    raise NotImplementedError("ls: implemented in change #1")


@app.command()
def show(slug: str) -> None:
    """Show SKILL.md content and sources.yml for a slug."""
    raise NotImplementedError("show: implemented in change #1")


if __name__ == "__main__":
    app()
