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
from skill_forge.import_skill import (
    SkillImportError,
    SkillImportErrorGroup,
    import_directory,
    import_file,
)
from skill_forge.models import JUDGE_AXES, JudgeFinding, JudgeScore, Skill
from skill_forge.providers.anthropic import AnthropicProvider
from skill_forge.providers.base import LLMProvider, LLMProviderError
from skill_forge.providers.claude_code import ClaudeCodeProvider
from skill_forge.storage import filesystem as storage
from skill_forge.storage.filesystem import free_slug, read_skill_file

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

    slug = free_slug(root, skill.name)
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


OriginTagOpt = Annotated[
    str | None,
    typer.Option(
        "--origin-tag",
        help="Provenance label (e.g. external/claude-code, microsoft/skills, manual).",
    ),
]


@app.command(name="import")
def import_command(
    path: Path,
    origin_tag: OriginTagOpt = None,
    root: RootOpt = None,
) -> None:
    """Import an existing SKILL.md from disk into skills/_draft/."""
    base = _resolve_root(root)
    identity = _load_identity(home=None)
    try:
        skill, sources = import_file(base, path, identity=identity, origin_tag=origin_tag)
    except SkillImportError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Imported: {skill.name}")
    typer.echo(f"  Draft path: skills/_draft/{skill.name}/SKILL.md")
    typer.echo(f"  Sources:    sources/{skill.name}.yml ({sources[0].url})")


@app.command(name="import-dir")
def import_dir_command(
    src_dir: Path,
    origin_tag: OriginTagOpt = None,
    root: RootOpt = None,
) -> None:
    """Bulk-import every subdirectory containing a SKILL.md."""
    base = _resolve_root(root)
    identity = _load_identity(home=None)
    try:
        results = import_directory(base, src_dir, identity=identity, origin_tag=origin_tag)
    except SkillImportErrorGroup as exc:
        for failure in exc.failures:
            typer.echo(f"failed: {failure}", err=True)
        typer.echo(
            f"\n{len(exc.failures)} import(s) failed. "
            "Any skills that parsed cleanly still landed in skills/_draft/.",
            err=True,
        )
        raise typer.Exit(code=1) from exc
    except SkillImportError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for skill, _ in results:
        typer.echo(f"Imported: {skill.name}")
    typer.echo(f"\n{len(results)} skill(s) imported.")


@app.command()
def judge(slug: str, root: RootOpt = None) -> None:
    """Score a skill against the configured rubric."""
    from skill_forge.evaluation.judge import judge_skill

    base = _resolve_root(root)
    cfg = load_config(base)
    weights: dict[str, float] = cfg["rubric"]["weights"]
    promotion = cfg["promotion"]
    provider_name = cfg["providers"]["judge"]

    if provider_name == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        typer.echo(
            "ANTHROPIC_API_KEY not set; switch `providers.judge` to 'claude_code' "
            "in config/default.yml or export the key.",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        provider = _build_provider(provider_name, cfg)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    identity = _load_identity(home=None)
    try:
        score, findings = judge_skill(
            base, slug, provider=provider, weights=weights, identity=identity
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except LLMProviderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc

    _print_judge_result(slug, score, findings, promotion)


def _print_judge_result(
    slug: str,
    score: JudgeScore,
    findings: list[JudgeFinding],
    promotion: dict[str, float],
) -> None:
    total_min = float(promotion.get("total_min", 0.75))
    axis_min = float(promotion.get("axis_min", 0.50))
    typer.echo(f"Judging: {slug}")
    for axis in JUDGE_AXES:
        value = getattr(score, axis)
        mark = "✓" if value >= axis_min else "✗"
        typer.echo(f"  {axis:<20} {value:.2f}  {mark}")
    typer.echo(f"  {'─' * 28}")
    total_mark = "✓" if score.total >= total_min else "✗"
    typer.echo(f"  {'total':<20} {score.total:.2f}  {total_mark}  (threshold {total_min:.2f})")
    if findings:
        typer.echo("")
        typer.echo("Findings:")
        for f in findings:
            typer.echo(f"  [{f.severity}] {f.axis}: {f.observation}")
    verdict = "ready to promote" if score.total >= total_min else "stays in draft"
    typer.echo(f"\nResult: {verdict}.")


@app.command()
def run(topic: str) -> None:
    """Run the full pipeline: discover -> extract -> judge -> promote."""
    raise NotImplementedError("run: implemented in change #4")


@app.command()
def promote(
    slug: str,
    force: Annotated[bool, typer.Option("--force", help="Bypass the threshold check.")] = False,
    root: RootOpt = None,
) -> None:
    """Move a draft to live (subject to the configured judge threshold)."""
    from skill_forge.promotion.promoter import (
        AlreadyPromotedError,
        BelowThresholdError,
        NotJudgedError,
    )
    from skill_forge.promotion.promoter import promote as _promote

    base = _resolve_root(root)
    cfg = load_config(base)
    identity = _load_identity(home=None)
    try:
        path = _promote(
            base, slug, promotion=cfg["promotion"], force=force, identity=identity
        )
    except NotJudgedError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except (BelowThresholdError, AlreadyPromotedError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Promoted: {slug}")
    typer.echo(f"  Live path: {path.relative_to(base)}")


@app.command()
def demote(
    slug: str,
    reason: Annotated[str, typer.Option("--reason", "-r", help="Why this skill is being demoted.")],
    root: RootOpt = None,
) -> None:
    """Move a live skill back to draft, with a reason recorded in the audit log."""
    from skill_forge.promotion.promoter import (
        DemoteCollisionError,
        NotLiveError,
    )
    from skill_forge.promotion.promoter import demote as _demote

    base = _resolve_root(root)
    identity = _load_identity(home=None)
    try:
        path = _demote(base, slug, reason=reason, identity=identity)
    except (NotLiveError, DemoteCollisionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Demoted: {slug}")
    typer.echo(f"  Draft path: {path.relative_to(base)}")
    typer.echo(f"  Reason:     {reason}")


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
            skill: Skill = read_skill_file(skill_md)
        except (ValueError, OSError) as exc:
            failures.append(f"failed to parse {skill_md}: {exc}")
            continue
        if skill.origin is not None and not skill.origin.startswith(f"{identity.instance_id}:"):
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
            storage.write_skill(base, skill, draft=is_draft, identity=identity, overwrite=True)
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
