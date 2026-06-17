"""`forge gold` (human attestation) + `forge tier` (derived trust tier)."""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from skill_forge.audit import append_calibration, latest_calibration, latest_event
from skill_forge.cli import (
    GoldHomeOpt,
    RootOpt,
    _die,
    _provider_or_exit,
    _resolve_gold_home,
    _resolve_root,
    app,
)
from skill_forge.config import load as load_config
from skill_forge.models import CalibrationRecord, GoldAttestation
from skill_forge.storage import filesystem as storage
from skill_forge.trust import compute_tier, gold_valid_for


@app.command()
def gold(slug: str, gold_home: GoldHomeOpt = None, root: RootOpt = None) -> None:
    """Attest `slug` as gold — a human vouch signed with the gold key (separate
    from the instance auto-signature). Only a live, judged, signed skill."""
    from skill_forge.identity import get_or_create, public_key_pem, sign_gold

    base = _resolve_root(root)
    live = base / "skills" / slug / "SKILL.md"
    if not live.is_file():
        _die(f"{slug!r} is not live; only live skills can be gold-attested.", 1)
    if latest_event(base, slug, "judged") is None:
        _die(f"{slug!r} has not been judged; run `forge judge {slug}` first.", 1)
    skill = storage.read_skill_file(live)
    if skill.origin is None:
        _die(f"{slug!r} is unsigned (no origin); cannot attest.", 1)

    g = get_or_create(_resolve_gold_home(gold_home))
    attestation = GoldAttestation(
        skill_origin=skill.origin,
        version=skill.version,
        gold_public_key=public_key_pem(g),
        signature=sign_gold(g, skill_origin=skill.origin, version=skill.version),
        attested_at=datetime.now(UTC),
    )
    sources = storage.read_sources(base, slug)
    updated = sources.model_copy(update={"gold": attestation})
    storage.write_sources(base, slug, updated, overwrite=True)
    typer.echo(f"Gold: {slug} attested for v{skill.version} (gold key {g.instance_id})")


@app.command()
def calibrate(root: RootOpt = None) -> None:
    """Re-judge the gold set (+ optional weak fixtures) to check the grader is
    still in-spec, and record the result. Exit 2 below `calibrate.min_gold`."""
    from skill_forge.evaluation.calibration import (
        calibrate as run_calibration,
    )
    from skill_forge.evaluation.calibration import (
        collect_gold_set,
        collect_weak_fixtures,
    )

    base = _resolve_root(root)
    cfg = load_config(base)
    cal_cfg = cfg.get("calibrate", {}) or {}
    min_gold = int(cal_cfg.get("min_gold", 3))

    golds = collect_gold_set(base)
    if len(golds) < min_gold:
        _die(f"insufficient gold set: {len(golds)} < {min_gold}", 2)

    weak_raw = cal_cfg.get("weak_dir")
    weak = collect_weak_fixtures(base / weak_raw if weak_raw else None)

    judge_cfg = cfg.get("judge", {}) or {}
    provider = _provider_or_exit(cfg, "judge")
    record = run_calibration(
        golds, weak,
        provider=provider,
        weights=cfg["rubric"]["weights"],
        total_min=float(cfg["promotion"].get("total_min", 0.75)),
        runs=int(judge_cfg.get("runs", 3)),
        temperature=float(judge_cfg.get("temperature", 0.0)),
        rubric_version=str(cfg["rubric"].get("version", "2")),
    )
    append_calibration(base, record)
    _print_calibration(record)


def _print_calibration(record: CalibrationRecord) -> None:
    status = "PASS" if record.passed else "FAIL"
    typer.echo(
        f"Calibration: {status}  agreement {record.agreement:.0%}  "
        f"({len(record.results)} samples, rubric {record.rubric_version}, model {record.model_id})"
    )
    for s in record.results:
        mark = "✓" if s.correct else "✗"
        typer.echo(f"  {mark} {s.slug} v{s.version}  total {s.total:.2f}  (expected {s.expected})")


@app.command()
def tier(slug: str, root: RootOpt = None) -> None:
    """Print the derived trust tier for `slug` and the evidence behind it."""
    base = _resolve_root(root)
    promotion = load_config(base)["promotion"]
    total_min = float(promotion.get("total_min", 0.75))
    axis_min = float(promotion.get("axis_min", 0.50))
    calibration = latest_calibration(base, passing=True)
    derived = compute_tier(
        base, slug, total_min=total_min, axis_min=axis_min, calibration=calibration
    )

    typer.echo(f"{slug}: {derived}")
    judged = latest_event(base, slug, "judged")
    if judged is not None and judged.scores is not None:
        version = judged.judge_provenance.rubric_version if judged.judge_provenance else "?"
        typer.echo(f"  judged total {judged.scores.total:.2f} (rubric {version})")
    if derived == "silver" and calibration is not None:
        typer.echo(
            f"  calibrated {calibration.calibrated_at.date()} "
            f"(rubric {calibration.rubric_version}, agreement {calibration.agreement:.0%})"
        )
    if gold_valid_for(base, slug):
        att = storage.read_sources(base, slug).gold
        if att is not None:
            typer.echo(f"  gold attested {att.attested_at.date()} for v{att.version}")
