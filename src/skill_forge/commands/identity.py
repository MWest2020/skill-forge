"""`forge identity show`, `identity backfill` — manage the signing keypair."""

from __future__ import annotations

from typing import Annotated

import typer

from skill_forge.cli import (
    HomeOpt,
    RootOpt,
    _die,
    _load_identity,
    _resolve_home,
    _resolve_root,
    identity_app,
)
from skill_forge.identity import get_or_create
from skill_forge.models import Skill
from skill_forge.storage import filesystem as storage
from skill_forge.storage.filesystem import read_skill_file


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
        _die(f"cannot read or create identity at {base}: {exc}", 1)

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
