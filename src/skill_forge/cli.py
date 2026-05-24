"""`forge` CLI entrypoint for the skill-forge project."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from skill_forge.config import load as load_config
from skill_forge.extraction import distiller
from skill_forge.extraction.fetcher import DEFAULT_MAX_PAGES, FetchError, fetch
from skill_forge.identity import Identity, get_or_create
from skill_forge.models import Skill
from skill_forge.providers.anthropic import AnthropicProvider
from skill_forge.providers.base import LLMProvider, LLMProviderError
from skill_forge.providers.claude_code import ClaudeCodeProvider
from skill_forge.storage import filesystem as storage
from skill_forge.storage.filesystem import _read_skill_file

DEFAULT_HOME = Path.home() / ".config" / "skill-forge"

app = typer.Typer(
    name="forge",
    help="Distill sources into reusable SKILL.md files.",
    no_args_is_help=True,
)
identity_app = typer.Typer(
    name="identity",
    help="Manage this instance's keypair and signature backfill.",
    no_args_is_help=True,
)
app.add_typer(identity_app, name="identity")

RootOpt = Annotated[
    Path | None,
    typer.Option("--root", help="Project root containing the skills/ tree."),
]
HomeOpt = Annotated[
    Path | None,
    typer.Option(
        "--home",
        help="Override identity home (default: $SKILL_FORGE_HOME or ~/.config/skill-forge).",
    ),
]


def _resolve_root(root: Path | None) -> Path:
    return root if root is not None else Path.cwd()


def _resolve_home(home: Path | None) -> Path:
    if home is not None:
        return home
    env = os.environ.get("SKILL_FORGE_HOME")
    return Path(env) if env else DEFAULT_HOME


def _load_identity(home: Path | None) -> Identity:
    return get_or_create(_resolve_home(home))


@app.command()
def discover(topic: str) -> None:
    """Find candidate sources for a topic and filter by license."""
    raise NotImplementedError("discover: implemented in change #4")


@app.command()
def extract(
    source_url: str,
    follow_all: Annotated[
        bool,
        typer.Option("--all", help='Follow rel="next" pagination chains.'),
    ] = False,
    max_pages: Annotated[
        int,
        typer.Option("--max-pages", help="Cap on pages followed during --all."),
    ] = DEFAULT_MAX_PAGES,
    root: RootOpt = None,
) -> None:
    """Fetch a source and distill it into a draft SKILL.md."""
    base = _resolve_root(root)
    cfg = load_config(base)
    provider_name = cfg["providers"]["extract"]
    if provider_name == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        typer.echo(
            "ANTHROPIC_API_KEY not set. Add it to .env or export it, "
            "or switch `providers.extract` to 'claude_code' in config/default.yml.",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        provider = _build_provider(provider_name, cfg)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    identity = _load_identity(home=None)
    _run_extract(
        source_url,
        root=base,
        follow_next=follow_all,
        max_pages=max_pages,
        provider=provider,
        identity=identity,
    )


def _build_provider(name: str, cfg: dict[str, object]) -> LLMProvider:
    if name == "anthropic":
        anth = cfg.get("anthropic", {}) or {}
        assert isinstance(anth, dict)
        return AnthropicProvider(
            model=str(anth.get("model", "claude-opus-4-7")),
            max_tokens=int(anth.get("max_tokens", 4096)),
        )
    if name == "claude_code":
        cc = cfg.get("claude_code", {}) or {}
        assert isinstance(cc, dict)
        return ClaudeCodeProvider(
            binary=str(cc.get("binary", "claude")),
            timeout=float(cc.get("timeout_s", 120)),
        )
    raise ValueError(f"unknown provider: {name!r} (expected 'anthropic' or 'claude_code')")


def _run_extract(
    source_url: str,
    *,
    root: Path,
    follow_next: bool,
    max_pages: int,
    provider: LLMProvider,
    identity: Identity | None = None,
) -> None:
    """Shared extract logic (testable without going through typer)."""
    try:
        content = fetch(source_url, follow_next=follow_next, max_pages=max_pages)
    except FetchError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except (FileNotFoundError, PermissionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    try:
        skill, sources = distiller.distill(content, provider=provider)
    except LLMProviderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc

    slug = _free_slug(root, skill.name)
    if slug != skill.name:
        skill = skill.model_copy(update={"name": slug})

    draft_path = storage.write_skill(root, skill, draft=True, identity=identity)
    from skill_forge.models import SourcesFile

    sources_file = SourcesFile(slug=slug, sources=sources, runs=[])
    sources_path = storage.write_sources(root, slug, sources_file)

    typer.echo(f"Drafted: {slug}")
    typer.echo(f"  Pages fetched: {len(content.pages)}")
    typer.echo(f"  Draft path:    {draft_path.relative_to(root)}")
    typer.echo(f"  Sources:       {sources_path.relative_to(root)}")
    for blocked in content.blocked:
        typer.echo(f"  Blocked:       {blocked}")


def _free_slug(root: Path, base: str) -> str:
    candidate = base
    n = 1
    while _slug_exists(root, candidate):
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def _slug_exists(root: Path, slug: str) -> bool:
    live = root / "skills" / slug / "SKILL.md"
    draft = root / "skills" / "_draft" / slug / "SKILL.md"
    return live.is_file() or draft.is_file()


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


@identity_app.command(name="show")
def identity_show(home: HomeOpt = None) -> None:
    """Print this instance's ID, public key, and private-key location."""
    from cryptography.hazmat.primitives import serialization

    base = _resolve_home(home)
    priv_path = base / "identity" / "private_key.pem"
    just_generated = not priv_path.is_file()
    try:
        identity = get_or_create(base)
    except OSError as exc:
        typer.echo(f"cannot read or create identity at {base}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if just_generated:
        typer.echo("Generated new identity. Back up the private key now.")
    pub_pem = identity.public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    typer.echo(f"Instance ID: {identity.instance_id}")
    typer.echo("Public key:")
    typer.echo(pub_pem.rstrip())
    typer.echo(f"Private key: {priv_path}")
    typer.echo("             (mode 0600 — back this file up; losing it breaks signing)")


@identity_app.command(name="backfill")
def identity_backfill(
    root: RootOpt = None,
    home: HomeOpt = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the plan, write nothing."),
    ] = False,
) -> None:
    """Stamp origin + signature on existing skills that lack them."""
    base = _resolve_root(root)
    identity = _load_identity(home)

    failures: list[str] = []
    for skill_md in sorted(base.glob("skills/**/SKILL.md")):
        try:
            skill: Skill = _read_skill_file(skill_md)
        except (ValueError, OSError) as exc:
            failures.append(f"failed to parse {skill_md}: {exc}")
            continue
        if skill.origin is not None and not skill.origin.startswith(
            f"{identity.instance_id}:"
        ):
            typer.echo(f"skipped: {skill_md.relative_to(base)}  foreign origin")
            continue
        if skill.origin is not None and skill.signature is not None:
            typer.echo(f"skipped: {skill_md.relative_to(base)}  already signed")
            continue
        if dry_run:
            typer.echo(f"would stamp: {skill_md.relative_to(base)}")
            continue
        is_draft = (base / "skills" / "_draft") in skill_md.parents
        try:
            storage.write_skill(
                base, skill, draft=is_draft, identity=identity, overwrite=True
            )
        except (ValueError, OSError) as exc:
            failures.append(f"failed to stamp {skill_md}: {exc}")
            continue
        typer.echo(
            f"stamped: {skill_md.relative_to(base)}  "
            f"origin={identity.instance_id}:{skill.name}:{skill.version}"
        )
    if failures:
        for msg in failures:
            typer.echo(msg, err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
