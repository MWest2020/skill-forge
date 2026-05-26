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

lineage_app = typer.Typer(
    name="lineage",
    help="Manage skill iteration lineage (migrate, verify).",
    no_args_is_help=True,
)
app.add_typer(lineage_app, name="lineage")

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
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

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
) -> None:
    """Discover top-N candidates for a topic, extract each, judge each."""
    from skill_forge.discovery.github import GitHubSearchError, search_repos
    from skill_forge.discovery.license_check import classify_spdx

    base = _resolve_root(root)
    cfg = load_config(base)
    provider_name = cfg["providers"]["extract"]
    if provider_name == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        typer.echo("ANTHROPIC_API_KEY not set.", err=True)
        raise typer.Exit(code=2)
    try:
        provider = _build_provider(provider_name, cfg)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    try:
        candidates = search_repos(topic, limit=max_candidates * 3)
    except GitHubSearchError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    allowed = [c for c in candidates if classify_spdx(c.spdx_license) != "forbidden"][
        :max_candidates
    ]
    if not allowed:
        typer.echo(f"No license-clean candidates found for {topic!r}.", err=True)
        raise typer.Exit(code=1)

    identity = _load_identity(home=None)
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


@app.command(name="import-repo")
def import_repo_command(
    url: str,
    origin_tag: OriginTagOpt = None,
    ref: Annotated[
        str | None, typer.Option("--ref", help="Branch or commit SHA (default: repo HEAD)")
    ] = None,
    max_skills: Annotated[
        int, typer.Option("--max-skills", help="Refuse repos with more than this many SKILL.md")
    ] = 50,
    root: RootOpt = None,
) -> None:
    """Walk a GitHub repo and import every SKILL.md found inside it."""
    from skill_forge.import_skill import RepoImportError, import_github_repo

    base = _resolve_root(root)
    identity = _load_identity(home=None)
    try:
        result = import_github_repo(
            base,
            url,
            identity=identity,
            origin_tag=origin_tag,
            ref=ref,
            max_skills=max_skills,
        )
    except RepoImportError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for skill in result.imported:
        typer.echo(f"  imported: {skill.name}")
    for path, reason in result.skipped:
        typer.echo(f"  skipped:  {path}  ({reason[:80]})", err=True)
    typer.echo(f"\n{len(result.imported)} imported, {len(result.skipped)} skipped from {url}")


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
        path = _promote(base, slug, promotion=cfg["promotion"], force=force, identity=identity)
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


@app.command()
def refine(
    slug: str,
    with_source: Annotated[
        str | None,
        typer.Option(
            "--with-source",
            help="Optional URL or file path with new material to fold in.",
        ),
    ] = None,
    hint: Annotated[
        str | None,
        typer.Option("--prompt", help="User-supplied steer for the refinement."),
    ] = None,
    root: RootOpt = None,
) -> None:
    """Generate a new iteration of a skill from its latest judge findings."""
    from skill_forge.extraction.fetcher import fetch
    from skill_forge.refinement import (
        NoJudgmentToRefineError,
        PendingIterationExistsError,
        RefinementError,
        refine_skill,
    )

    base = _resolve_root(root)
    cfg = load_config(base)
    provider_name = cfg["providers"]["judge"]
    if provider_name == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        typer.echo("ANTHROPIC_API_KEY not set.", err=True)
        raise typer.Exit(code=2)
    try:
        provider = _build_provider(provider_name, cfg)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    extra_text: str | None = None
    if with_source:
        try:
            content = fetch(with_source, follow_next=False)
            extra_text = "\n\n".join(
                p.body.decode("utf-8", errors="replace") for p in content.pages
            )
        except (FileNotFoundError, OSError, FetchError) as exc:
            typer.echo(f"--with-source fetch failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    identity = _load_identity(home=None)
    try:
        new_version = refine_skill(
            base,
            slug,
            provider=provider,
            identity=identity,
            hint=hint,
            extra_source=extra_text,
        )
    except NoJudgmentToRefineError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except PendingIterationExistsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except (RefinementError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except LLMProviderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc

    typer.echo(f"Refined: {slug} → v{new_version} (pending)")
    typer.echo(f"  Review with: forge diff {slug}")
    typer.echo(f"  Accept with: forge refine-accept {slug} --iteration {new_version}")
    typer.echo(f"  Reject with: forge refine-reject {slug} --iteration {new_version} --reason ...")


@app.command(name="refine-accept")
def refine_accept(
    slug: str,
    iteration: Annotated[int, typer.Option("--iteration", help="Iteration version to accept.")],
    root: RootOpt = None,
) -> None:
    """Promote a pending iteration to be the current SKILL.md."""
    from skill_forge.refinement import RefinementError, accept_iteration

    base = _resolve_root(root)
    identity = _load_identity(home=None)
    try:
        path = accept_iteration(base, slug, version=iteration, identity=identity)
    except (RefinementError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Accepted: {slug} → v{iteration} is now current")
    typer.echo(f"  Path: {path.relative_to(base)}")


@app.command(name="refine-reject")
def refine_reject(
    slug: str,
    iteration: Annotated[int, typer.Option("--iteration", help="Iteration version to reject.")],
    reason: Annotated[str, typer.Option("--reason", "-r", help="Why this iteration is rejected.")],
    root: RootOpt = None,
) -> None:
    """Mark a pending iteration as rejected. File stays on disk for audit."""
    from skill_forge.refinement import RefinementError, reject_iteration

    base = _resolve_root(root)
    try:
        reject_iteration(base, slug, version=iteration, reason=reason)
    except (RefinementError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Rejected: {slug} v{iteration}")
    typer.echo(f"  Reason: {reason}")


@app.command()
def diff(
    slug: str,
    from_version: Annotated[
        int | None, typer.Option("--from", help="From-version (default: current - 1).")
    ] = None,
    to_version: Annotated[
        int | None, typer.Option("--to", help="To-version (default: current).")
    ] = None,
    root: RootOpt = None,
) -> None:
    """Show a unified diff between two iterations of a skill."""
    import difflib
    import shutil as _shutil
    import subprocess
    import sys

    base = _resolve_root(root)
    draft = not (base / "skills" / slug / "SKILL.md").is_file()
    try:
        lineage = storage.read_lineage(base, slug, draft=draft)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    # Default --to to the highest version on disk (covers pending iterations),
    # not just current_version. Default --from to to_v - 1.
    highest = max(it.version for it in lineage.iterations)
    to_v = to_version if to_version is not None else highest
    from_v = from_version if from_version is not None else to_v - 1
    if from_v < 1 or to_v < 1 or from_v == to_v:
        typer.echo(
            "no prior iteration to diff against (only one version exists)",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        from_path = next(storage.iterations_dir(base, slug, draft=draft).glob(f"v{from_v}-*.md"))
        to_path = next(storage.iterations_dir(base, slug, draft=draft).glob(f"v{to_v}-*.md"))
    except (StopIteration, FileNotFoundError) as exc:
        typer.echo(f"iteration v{from_v} or v{to_v} not found", err=True)
        raise typer.Exit(code=1) from exc

    if _shutil.which("git"):
        # Only force color when stdout is a TTY — otherwise piped output gets
        # literal ANSI escape codes.
        color = "always" if sys.stdout.isatty() else "never"
        subprocess.run(
            ["git", "diff", "--no-index", f"--color={color}", str(from_path), str(to_path)],
            check=False,
        )
    else:
        from_lines = from_path.read_text().splitlines(keepends=True)
        to_lines = to_path.read_text().splitlines(keepends=True)
        diff_lines = difflib.unified_diff(
            from_lines, to_lines, fromfile=str(from_path), tofile=str(to_path)
        )
        for line in diff_lines:
            typer.echo(line, nl=False)


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
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
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


serve_app = typer.Typer(
    name="serve",
    help="Run skill-forge as a server (MCP).",
    no_args_is_help=True,
)
app.add_typer(serve_app, name="serve")

peer_app = typer.Typer(
    name="peer",
    help="Manage federation peers and pull skills from them.",
    no_args_is_help=True,
)
app.add_typer(peer_app, name="peer")


@app.command()
def subscribe(
    slug: Annotated[
        str | None, typer.Argument(help="Skill slug to subscribe to (omit with --list).")
    ] = None,
    list_only: Annotated[bool, typer.Option("--list", help="List watched sources.")] = False,
    remove: Annotated[bool, typer.Option("--remove", help="Drop a slug from watches.")] = False,
    root: RootOpt = None,
) -> None:
    """Watch a skill's source URL for changes."""
    from datetime import UTC, datetime

    from skill_forge.subscribe import (
        Subscription,
        SubscriptionError,
        add_subscription,
        list_subscriptions,
        remove_subscription,
    )

    base = _resolve_root(root)
    if list_only:
        subs = list_subscriptions(base)
        if not subs:
            typer.echo("No subscriptions. Add one: `forge subscribe <slug>`")
            return
        for s in subs:
            typer.echo(f"  {s.slug:<35} {s.url}  (checked: {s.last_checked.isoformat()})")
        return
    if slug is None:
        typer.echo("missing argument: SLUG (or use --list)", err=True)
        raise typer.Exit(code=1)
    if remove:
        if remove_subscription(base, slug):
            typer.echo(f"Unsubscribed: {slug}")
        else:
            typer.echo(f"No subscription named {slug!r}", err=True)
            raise typer.Exit(code=1)
        return
    try:
        sources = storage.read_sources(base, slug)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    http_source = next(
        (s for s in sources.sources if s.url.startswith(("http://", "https://"))),
        None,
    )
    if http_source is None:
        typer.echo(
            f"{slug!r} has no http(s) source to subscribe to "
            "(local-author and federation sources aren't refetchable)",
            err=True,
        )
        raise typer.Exit(code=1)
    sub = Subscription(
        slug=slug,
        url=http_source.url,
        last_sha256=http_source.sha256,
        last_checked=datetime.now(UTC),
    )
    try:
        add_subscription(base, sub)
    except SubscriptionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Subscribed: {slug} → {http_source.url}")


@app.command(name="check-updates")
def check_updates(root: RootOpt = None) -> None:
    """Re-fetch every watched source URL, report changes."""
    from skill_forge.subscribe import check_updates as _check

    base = _resolve_root(root)
    results = _check(base)
    if not results:
        typer.echo("No subscriptions to check. Add one: `forge subscribe <slug>`")
        return
    changed = sum(1 for r in results if r.status == "changed")
    unreachable = sum(1 for r in results if r.status == "unreachable")
    for r in results:
        marker = {"unchanged": "·", "changed": "↻", "unreachable": "✗"}[r.status]
        line = f"  {marker} {r.slug:<35} {r.status}"
        if r.status == "unreachable" and r.error:
            line += f"  ({r.error[:60]})"
        typer.echo(line)
    typer.echo(
        f"\n{len(results)} checked: {changed} changed, "
        f"{unreachable} unreachable, {len(results) - changed - unreachable} unchanged."
    )


@peer_app.command(name="add")
def peer_add(
    name: str,
    url: str,
    token: Annotated[
        str | None, typer.Option("--token", help="Bearer token for peer's MCP HTTP.")
    ] = None,
    trust: Annotated[
        str, typer.Option("--trust", help="reference-only | review-queue")
    ] = "reference-only",
    root: RootOpt = None,
) -> None:
    """Register a federation peer."""
    from skill_forge.federation import Peer, PeerError, add_peer

    base = _resolve_root(root)
    try:
        add_peer(base, Peer(name=name, url=url, token=token, trust_mode=trust))
    except (PeerError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Added peer: {name} → {url} (trust: {trust})")
    typer.echo(
        "  Note: peer identity (instance ID + pubkey) is fetched on first pull "
        "and pinned via TOFU. Verify out-of-band before pulling sensitive skills."
    )


@peer_app.command(name="list")
def peer_list(root: RootOpt = None) -> None:
    """Show known peers."""
    from skill_forge.federation import list_peers

    base = _resolve_root(root)
    peers = list_peers(base)
    if not peers:
        typer.echo("No peers registered. Add one with: forge peer add <name> <url>")
        return
    for peer in peers:
        iid = peer.instance_id or "(not yet contacted)"
        typer.echo(f"  {peer.name:<20} {peer.url}  {iid}  [{peer.trust_mode}]")


@peer_app.command(name="remove")
def peer_remove(name: str, root: RootOpt = None) -> None:
    """Drop a peer from the registry."""
    from skill_forge.federation import remove_peer

    base = _resolve_root(root)
    if remove_peer(base, name):
        typer.echo(f"Removed peer: {name}")
    else:
        typer.echo(f"No peer named {name!r}", err=True)
        raise typer.Exit(code=1)


@peer_app.command(name="skills")
def peer_skills(name: str, root: RootOpt = None) -> None:
    """List skills a peer is willing to share."""
    from skill_forge.federation import PullError, fetch_manifest, list_peers

    base = _resolve_root(root)
    peer = next((p for p in list_peers(base) if p.name == name), None)
    if peer is None:
        typer.echo(f"No peer named {name!r}", err=True)
        raise typer.Exit(code=1)
    try:
        skills = fetch_manifest(peer)
    except PullError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if not skills:
        typer.echo(f"{name} has no public skills.")
        return
    for s in skills:
        score = s.get("judge_score")
        score_s = f"{score:.2f}" if isinstance(score, int | float) else "—"
        typer.echo(f"  {s['slug']:<35} score={score_s}  {s.get('description', '')[:60]}")


@peer_app.command(name="pull")
def peer_pull(
    name: str,
    slug: str,
    root: RootOpt = None,
) -> None:
    """Pull one skill by slug from a peer; verify signature; land as draft."""
    from skill_forge.federation import PullError, list_peers, pull_skill

    base = _resolve_root(root)
    peer = next((p for p in list_peers(base) if p.name == name), None)
    if peer is None:
        typer.echo(f"No peer named {name!r}", err=True)
        raise typer.Exit(code=1)
    try:
        skill = pull_skill(base, peer, slug)
    except PullError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Pulled: {skill.name} (origin: {skill.origin})")
    typer.echo(f"  Landed at: skills/_draft/{skill.name}/SKILL.md")


@serve_app.command(name="mcp")
def serve_mcp(
    transport: Annotated[str, typer.Option("--transport", help="stdio | http")] = "stdio",
    host: Annotated[str, typer.Option("--host", help="HTTP bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="HTTP bind port.")] = 8765,
    token: Annotated[
        str | None,
        typer.Option(
            "--token",
            help="Bearer token for HTTP; falls back to SKILL_FORGE_MCP_TOKEN env var.",
        ),
    ] = None,
    root: RootOpt = None,
) -> None:
    """Expose promoted skills as MCP resources (stdio or HTTP)."""
    from skill_forge.mcp import serve_http, serve_stdio

    base = _resolve_root(root)
    if transport == "stdio":
        serve_stdio(base)
        return
    if transport == "http":
        try:
            serve_http(base, host=host, port=port, token=token)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        return
    typer.echo(f"unknown transport {transport!r}; pick 'stdio' or 'http'", err=True)
    raise typer.Exit(code=2)


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


if __name__ == "__main__":
    app()
