"""`forge import`, `import-repo`, `import-dir` — bring SKILL.md files in."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from skill_forge.cli import (
    HomeOpt,
    OriginTagOpt,
    RootOpt,
    _die,
    _load_identity,
    _resolve_root,
    app,
)
from skill_forge.import_skill import (
    SkillImportError,
    SkillImportErrorGroup,
    import_directory,
    import_file,
)


@app.command(name="import")
def import_command(
    path: Path,
    origin_tag: OriginTagOpt = None,
    root: RootOpt = None,
    home: HomeOpt = None,
) -> None:
    """Import an existing SKILL.md from disk into skills/_draft/."""
    base = _resolve_root(root)
    identity = _load_identity(home)
    try:
        skill, sources = import_file(base, path, identity=identity, origin_tag=origin_tag)
    except SkillImportError as exc:
        _die(str(exc), 1)
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
    home: HomeOpt = None,
) -> None:
    """Walk a GitHub repo and import every SKILL.md found inside it."""
    from skill_forge.import_skill import RepoImportError, import_github_repo

    base = _resolve_root(root)
    identity = _load_identity(home)
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
        _die(str(exc), 1)
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
    home: HomeOpt = None,
) -> None:
    """Bulk-import every subdirectory containing a SKILL.md."""
    base = _resolve_root(root)
    identity = _load_identity(home)
    try:
        results = import_directory(base, src_dir, identity=identity, origin_tag=origin_tag)
    except SkillImportErrorGroup as exc:
        for failure in exc.failures:
            typer.echo(f"failed: {failure}", err=True)
        _die(
            f"\n{len(exc.failures)} import(s) failed. "
            "Any skills that parsed cleanly still landed in skills/_draft/.",
            1,
        )
    except SkillImportError as exc:
        _die(str(exc), 1)
    for skill, _ in results:
        typer.echo(f"Imported: {skill.name}")
    typer.echo(f"\n{len(results)} skill(s) imported.")
