"""`forge` CLI entrypoint for the skill-forge project.

Defines the shared `app` (plus the `identity`/`lineage` sub-apps), the common
option types, and the small helper layer every command leans on. The
discover/run/extract commands live here because they are tied to the provider
machinery (`_build_provider`, patched by tests on this module). All other
commands live in `skill_forge.commands.*` and register themselves when that
package is imported at the bottom of this file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from skill_forge.config import load as load_config
from skill_forge.extraction import distiller
from skill_forge.extraction.fetcher import DEFAULT_MAX_PAGES, FetchError, fetch
from skill_forge.identity import Identity, get_or_create
from skill_forge.providers.anthropic import AnthropicProvider
from skill_forge.providers.base import LLMProvider, LLMProviderError
from skill_forge.providers.claude_code import ClaudeCodeProvider
from skill_forge.storage import filesystem as storage
from skill_forge.storage.filesystem import free_slug

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

lineage_app = typer.Typer(
    name="lineage",
    help="Manage skill iteration lineage (migrate, verify).",
    no_args_is_help=True,
)
app.add_typer(lineage_app, name="lineage")

serve_app = typer.Typer(
    name="serve",
    help="Serve the live library to other tools (read-only).",
    no_args_is_help=True,
)
app.add_typer(serve_app, name="serve")

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
OriginTagOpt = Annotated[
    str | None,
    typer.Option(
        "--origin-tag",
        help="Provenance label (e.g. external/claude-code, microsoft/skills, manual).",
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


def _die(msg: str, code: int) -> NoReturn:
    """Echo an error to stderr and exit with `code`. The one place the CLI's
    error-to-exit-code mapping lives; each call site keeps its `except` type
    and code visible, only the echo+raise mechanics are shared."""
    typer.echo(msg, err=True)
    raise typer.Exit(code=code)


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
    if name == "ollama":
        from skill_forge.providers.ollama import OllamaProvider

        ol = cfg.get("ollama", {}) or {}
        assert isinstance(ol, dict)
        host_raw = ol.get("host")
        host: str | None = host_raw if isinstance(host_raw, str) else None
        return OllamaProvider(
            host=host,
            model=str(ol.get("model", "llama3.1")),
            timeout=float(ol.get("timeout_s", 120)),
        )
    raise ValueError(
        f"unknown provider: {name!r} (expected 'anthropic', 'claude_code', or 'ollama')"
    )


def _provider_or_exit(cfg: dict[str, object], role: str) -> LLMProvider:
    """Resolve the configured provider for `role` ("extract" or "judge"), or
    exit(2) with a helpful message. Centralizes the preamble every LLM-backed
    command shared: read providers.<role>, guard the anthropic API key, build
    the provider, and map an unknown name to a clean exit."""
    providers = cfg["providers"]
    assert isinstance(providers, dict)
    name = str(providers[role])
    if name == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        _die(
            f"ANTHROPIC_API_KEY not set; switch `providers.{role}` to 'claude_code' "
            "in config/default.yml or export the key.",
            2,
        )
    try:
        return _build_provider(name, cfg)
    except ValueError as exc:
        _die(str(exc), 2)


@app.command()
def discover(
    topic: str,
    limit: Annotated[int, typer.Option("--limit", help="Max candidates to return.")] = 10,
    root: RootOpt = None,
) -> None:
    """Find candidate GitHub sources for a topic and classify their licenses."""
    from skill_forge.discovery.github import GitHubSearchError, search_repos
    from skill_forge.discovery.license_check import classify_spdx

    base = _resolve_root(root)
    try:
        candidates = search_repos(topic, limit=limit)
    except GitHubSearchError as exc:
        _die(str(exc), 1)

    blocked_log = base / "discovery_blocked.log"
    table = Table(title=f"candidates for {topic!r}")
    table.add_column("Repo", style="bold")
    table.add_column("License")
    table.add_column("URL")
    kept = 0
    for cand in candidates:
        bucket = classify_spdx(cand.spdx_license)
        if bucket == "forbidden":
            _append_blocked(blocked_log, cand.html_url, cand.spdx_license or "none")
            continue
        kept += 1
        badge = {
            "permissive": "[green]permissive[/green]",
            "copyleft": "[yellow]copyleft[/yellow]",
            "restrictive": "[red]restrictive[/red]",
        }[bucket]
        table.add_row(cand.full_name, f"{badge} ({cand.spdx_license})", cand.html_url)
    Console().print(table)
    typer.echo(
        f"\n{kept}/{len(candidates)} kept; {len(candidates) - kept} blocked "
        f"(see {blocked_log.name})."
    )


def _append_blocked(log_path: Path, url: str, reason: str) -> None:
    """One JSONL line per blocked candidate. JSON escapes guarantee
    parseability regardless of what's in url/reason."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    import json as _json
    from datetime import UTC
    from datetime import datetime as _dt

    entry = {"ts": _dt.now(UTC).isoformat(), "url": url, "reason": reason}
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(_json.dumps(entry) + "\n")


@app.command()
def run(
    topic: str,
    max_candidates: Annotated[
        int, typer.Option("--max-candidates", help="Cap on candidates to extract.")
    ] = 3,
    root: RootOpt = None,
    home: HomeOpt = None,
) -> None:
    """Discover top-N candidates for a topic, extract each, judge each."""
    from skill_forge.discovery.github import GitHubSearchError, search_repos
    from skill_forge.discovery.license_check import classify_spdx

    base = _resolve_root(root)
    cfg = load_config(base)
    provider = _provider_or_exit(cfg, "extract")
    try:
        candidates = search_repos(topic, limit=max_candidates * 3)
    except GitHubSearchError as exc:
        _die(str(exc), 1)

    allowed = [c for c in candidates if classify_spdx(c.spdx_license) != "forbidden"][
        :max_candidates
    ]
    if not allowed:
        _die(f"No license-clean candidates found for {topic!r}.", 1)

    identity = _load_identity(home)
    for cand in allowed:
        typer.echo(f"\n--- {cand.full_name} ({cand.spdx_license}) ---")
        try:
            _run_extract(
                cand.html_url,
                root=base,
                follow_next=False,
                max_pages=DEFAULT_MAX_PAGES,
                provider=provider,
                identity=identity,
            )
        except typer.Exit as exc:
            # Code 2 = config/auth broken → don't waste budget on remaining candidates.
            if exc.exit_code == 2:
                raise
            typer.echo(f"  extract failed (exit {exc.exit_code}); continuing.", err=True)


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
    home: HomeOpt = None,
) -> None:
    """Fetch a source and distill it into a draft SKILL.md."""
    base = _resolve_root(root)
    cfg = load_config(base)
    provider = _provider_or_exit(cfg, "extract")
    identity = _load_identity(home)
    _run_extract(
        source_url,
        root=base,
        follow_next=follow_all,
        max_pages=max_pages,
        provider=provider,
        identity=identity,
    )


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
        _die(str(exc), 1)
    except (FileNotFoundError, PermissionError) as exc:
        _die(str(exc), 1)

    try:
        skill, sources = distiller.distill(content, provider=provider)
    except LLMProviderError as exc:
        _die(str(exc), 3)

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


# Importing the command package registers every remaining command on `app` (and
# the identity/lineage sub-apps). Kept at the bottom so the option types and
# helpers above already exist when each command module imports them back.
from skill_forge import commands as _commands  # noqa: E402, F401

if __name__ == "__main__":
    app()
