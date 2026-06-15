"""`forge refine`, `refine-accept`, `refine-reject`, `diff` — iterate a skill
across versions."""

from __future__ import annotations

from typing import Annotated

import typer

from skill_forge.cli import (
    HomeOpt,
    RootOpt,
    _die,
    _load_identity,
    _provider_or_exit,
    _resolve_root,
    app,
)
from skill_forge.config import load as load_config
from skill_forge.extraction.fetcher import FetchError
from skill_forge.providers.base import LLMProviderError
from skill_forge.storage import filesystem as storage


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
    home: HomeOpt = None,
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
    provider = _provider_or_exit(cfg, "judge")

    extra_text: str | None = None
    if with_source:
        try:
            content = fetch(with_source, follow_next=False)
            extra_text = "\n\n".join(
                p.body.decode("utf-8", errors="replace") for p in content.pages
            )
        except (FileNotFoundError, OSError, FetchError) as exc:
            _die(f"--with-source fetch failed: {exc}", 1)

    identity = _load_identity(home)
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
        _die(str(exc), 2)
    except PendingIterationExistsError as exc:
        _die(str(exc), 2)
    except (RefinementError, FileNotFoundError) as exc:
        _die(str(exc), 1)
    except LLMProviderError as exc:
        _die(str(exc), 3)

    typer.echo(f"Refined: {slug} → v{new_version} (pending)")
    typer.echo(f"  Review with: forge diff {slug}")
    typer.echo(f"  Accept with: forge refine-accept {slug} --iteration {new_version}")
    typer.echo(f"  Reject with: forge refine-reject {slug} --iteration {new_version} --reason ...")


@app.command(name="refine-accept")
def refine_accept(
    slug: str,
    iteration: Annotated[int, typer.Option("--iteration", help="Iteration version to accept.")],
    root: RootOpt = None,
    home: HomeOpt = None,
) -> None:
    """Promote a pending iteration to be the current SKILL.md."""
    from skill_forge.refinement import RefinementError, accept_iteration

    base = _resolve_root(root)
    identity = _load_identity(home)
    try:
        path = accept_iteration(base, slug, version=iteration, identity=identity)
    except (RefinementError, FileNotFoundError) as exc:
        _die(str(exc), 1)
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
        _die(str(exc), 1)
    except ValueError as exc:
        _die(str(exc), 1)
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
        _die(str(exc), 1)

    # Default --to to the highest version on disk (covers pending iterations),
    # not just current_version. Default --from to to_v - 1.
    highest = max(it.version for it in lineage.iterations)
    to_v = to_version if to_version is not None else highest
    from_v = from_version if from_version is not None else to_v - 1
    if from_v < 1 or to_v < 1 or from_v == to_v:
        _die("no prior iteration to diff against (only one version exists)", 1)

    try:
        from_path = next(storage.iterations_dir(base, slug, draft=draft).glob(f"v{from_v}-*.md"))
        to_path = next(storage.iterations_dir(base, slug, draft=draft).glob(f"v{to_v}-*.md"))
    except (StopIteration, FileNotFoundError):
        _die(f"iteration v{from_v} or v{to_v} not found", 1)

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
