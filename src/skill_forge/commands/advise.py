"""`forge advise` — read-only judge / skill linter.

Runs the median-of-N judge on an imported slug *or* a raw SKILL.md path and
prints structured advice. Writes nothing — no promote, no audit, no state. The
path mode makes it a quality gate for skills you haven't adopted yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from skill_forge.cli import RootOpt, _die, _provider_or_exit, _resolve_root, app
from skill_forge.config import load as load_config
from skill_forge.import_skill import normalize_skill_md
from skill_forge.models import JUDGE_AXES, JudgeFinding, JudgeScore, Skill
from skill_forge.providers.base import LLMProviderError
from skill_forge.storage import filesystem as storage


@app.command()
def advise(
    target: str,
    runs: Annotated[
        int | None, typer.Option("--runs", help="Override judge.runs (N) for this call.")
    ] = None,
    root: RootOpt = None,
) -> None:
    """Score a skill read-only and print advice. `target` is an imported slug
    or a path to a raw SKILL.md. Writes nothing."""
    from skill_forge.evaluation.judge import score_skill

    base = _resolve_root(root)
    cfg = load_config(base)
    weights: dict[str, float] = cfg["rubric"]["weights"]
    promotion = cfg["promotion"]
    rubric_version = str(cfg["rubric"].get("version", "1"))
    judge_cfg = cfg.get("judge", {}) or {}
    n = runs if runs is not None else int(judge_cfg.get("runs", 3))
    if n < 1:
        _die(f"--runs must be >= 1, got {n}", 2)
    temperature = float(judge_cfg.get("temperature", 0.0))

    skill, label = _resolve_target(base, target)
    provider = _provider_or_exit(cfg, "judge")
    try:
        score, findings, _prov = score_skill(
            skill, provider=provider, weights=weights, runs=n,
            temperature=temperature, rubric_version=rubric_version,
        )
    except LLMProviderError as exc:
        _die(str(exc), 3)
    _print_advice(label, score, findings, promotion)


def _resolve_target(base: Path, target: str) -> tuple[Skill, str]:
    """A real file path wins; otherwise treat `target` as an imported slug."""
    path = Path(target)
    if path.is_file():
        try:
            text = normalize_skill_md(path.read_text(encoding="utf-8"))
            return storage.parse_skill_text(text, path), path.name
        except (ValueError, OSError) as exc:
            _die(f"could not parse {target!r} as a SKILL.md: {exc}", 1)
    try:
        return storage.read_skill(base, target), target
    except FileNotFoundError:
        _die(f"no skill or file {target!r} (no such slug, no such path).", 1)


def _print_advice(
    label: str,
    score: JudgeScore,
    findings: list[JudgeFinding],
    promotion: dict[str, float],
) -> None:
    total_min = float(promotion.get("total_min", 0.75))
    axis_min = float(promotion.get("axis_min", 0.50))
    typer.echo(f"Advice: {label}")
    flagged = {f.axis for f in findings}
    for axis in JUDGE_AXES:
        value = getattr(score, axis)
        mark = "✓" if value >= axis_min else "✗"
        typer.echo(f"  {axis:<20} {value:.2f}  {mark}")
    typer.echo(f"  {'─' * 28}")
    total_mark = "✓" if score.total >= total_min else "✗"
    typer.echo(f"  {'total':<20} {score.total:.2f}  {total_mark}  (threshold {total_min:.2f})")

    strengths = [a for a in JUDGE_AXES if getattr(score, a) >= axis_min and a not in flagged]
    if strengths:
        typer.echo("\nStrengths:")
        typer.echo(f"  - {', '.join(strengths)}  (clear, no findings)")
    if findings:
        typer.echo("\nWeaknesses & fixes:")
        for f in findings:
            typer.echo(f"  [{f.severity}] {f.axis}: {f.observation}")

    would = score.total >= total_min and all(getattr(score, a) >= axis_min for a in JUDGE_AXES)
    typer.echo(f"\nVerdict: {'would promote' if would else 'below threshold'}.")
