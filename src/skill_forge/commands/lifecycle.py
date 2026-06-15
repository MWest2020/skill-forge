"""`forge judge`, `promote`, `demote` — score a skill and move it across the
draft/live boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from skill_forge.audit import latest_event
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
def judge(
    slug: str,
    explain: Annotated[
        bool,
        typer.Option("--explain", help="Print the recorded provenance for the latest score."),
    ] = False,
    runs: Annotated[
        int | None,
        typer.Option("--runs", help="Override judge.runs (N) for this call."),
    ] = None,
    root: RootOpt = None,
    home: HomeOpt = None,
) -> None:
    """Score a skill against the configured rubric (N runs, per-axis median)."""
    from skill_forge.evaluation.judge import judge_skill

    base = _resolve_root(root)
    if explain:
        _explain_latest_judge(base, slug)
        return

    cfg = load_config(base)
    weights: dict[str, float] = cfg["rubric"]["weights"]
    promotion = cfg["promotion"]
    rubric_version = str(cfg["rubric"].get("version", "1"))
    judge_cfg = cfg.get("judge", {}) or {}
    n = runs if runs is not None else int(judge_cfg.get("runs", 3))
    if n < 1:
        _die(f"judge.runs must be >= 1, got {n}", 2)
    temperature = float(judge_cfg.get("temperature", 0.0))
    provider = _provider_or_exit(cfg, "judge")

    identity = _load_identity(home)
    try:
        score, findings = judge_skill(
            base, slug, provider=provider, weights=weights, identity=identity,
            runs=n, temperature=temperature, rubric_version=rubric_version,
        )
    except FileNotFoundError as exc:
        _die(str(exc), 1)
    except LLMProviderError as exc:
        _die(str(exc), 3)

    _print_judge_result(slug, score, findings, promotion)
    prov = latest_event(base, slug, "judged")
    if prov is not None and prov.judge_provenance is not None:
        p = prov.judge_provenance
        typer.echo(
            f"\njudged {p.runs}× (median), prompt {p.prompt_sha256[:12]}, model {p.model_id}"
        )


def _explain_latest_judge(base: Path, slug: str) -> None:
    event = latest_event(base, slug, "judged")
    if event is None or event.judge_provenance is None:
        _die(f"no judged record for {slug!r}; run `forge judge {slug}` first.", 1)
    p = event.judge_provenance
    typer.echo(f"Judge provenance for {slug} (run {event.run_id}):")
    typer.echo(f"  provider:       {p.provider}")
    typer.echo(f"  model:          {p.model_id}")
    typer.echo(f"  rubric version: {p.rubric_version}")
    typer.echo(f"  prompt sha256:  {p.prompt_sha256}")
    typer.echo(f"  temperature:    {p.temperature}")
    typer.echo(f"  runs:           {p.runs}")
    for i, axes in enumerate(p.raw_axes, 1):
        rendered = "  ".join(f"{a}={axes[a]:.2f}" for a in JUDGE_AXES)
        typer.echo(f"  run {i}: {rendered}")
    median = "  ".join(f"{a}={p.median_axes[a]:.2f}" for a in JUDGE_AXES)
    typer.echo(f"  median: {median}")


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
