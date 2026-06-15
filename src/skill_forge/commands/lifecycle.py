"""`forge judge`, `promote`, `demote` — score a skill and move it across the
draft/live boundary."""

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
from skill_forge.models import JUDGE_AXES, JudgeFinding, JudgeScore
from skill_forge.providers.base import LLMProviderError


@app.command()
def judge(slug: str, root: RootOpt = None, home: HomeOpt = None) -> None:
    """Score a skill against the configured rubric."""
    from skill_forge.evaluation.judge import judge_skill

    base = _resolve_root(root)
    cfg = load_config(base)
    weights: dict[str, float] = cfg["rubric"]["weights"]
    promotion = cfg["promotion"]
    provider = _provider_or_exit(cfg, "judge")

    identity = _load_identity(home)
    try:
        score, findings = judge_skill(
            base, slug, provider=provider, weights=weights, identity=identity
        )
    except FileNotFoundError as exc:
        _die(str(exc), 1)
    except LLMProviderError as exc:
        _die(str(exc), 3)

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
    home: HomeOpt = None,
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
    identity = _load_identity(home)
    try:
        path = _promote(base, slug, promotion=cfg["promotion"], force=force, identity=identity)
    except NotJudgedError as exc:
        _die(str(exc), 2)
    except (BelowThresholdError, AlreadyPromotedError, FileNotFoundError) as exc:
        _die(str(exc), 1)
    typer.echo(f"Promoted: {slug}")
    typer.echo(f"  Live path: {path.relative_to(base)}")


@app.command()
def demote(
    slug: str,
    reason: Annotated[str, typer.Option("--reason", "-r", help="Why this skill is being demoted.")],
    root: RootOpt = None,
    home: HomeOpt = None,
) -> None:
    """Move a live skill back to draft, with a reason recorded in the audit log."""
    from skill_forge.promotion.promoter import (
        DemoteCollisionError,
        NotLiveError,
    )
    from skill_forge.promotion.promoter import demote as _demote

    base = _resolve_root(root)
    identity = _load_identity(home)
    try:
        path = _demote(base, slug, reason=reason, identity=identity)
    except (NotLiveError, DemoteCollisionError) as exc:
        _die(str(exc), 1)
    except ValueError as exc:
        _die(str(exc), 1)
    typer.echo(f"Demoted: {slug}")
    typer.echo(f"  Draft path: {path.relative_to(base)}")
    typer.echo(f"  Reason:     {reason}")
