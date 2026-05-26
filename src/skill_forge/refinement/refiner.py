"""Refine a skill from judge findings; accept/reject pending iterations.

Specs:
- openspec/changes/add-refinement-loop/specs/refine/spec.md
- openspec/changes/add-refinement-loop/specs/accept-reject/spec.md
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.identity import Identity
from skill_forge.models import (
    Iteration,
    JudgeFinding,
    Lineage,
    RunEvent,
    Skill,
)
from skill_forge.providers.base import LLMProvider
from skill_forge.storage import filesystem as storage


class RefinementError(Exception):
    """Base for refinement-specific errors."""


class NoJudgmentToRefineError(RefinementError):
    """Refinement was called on a skill that has never been judged."""


class PendingIterationExistsError(RefinementError):
    """A pending iteration already exists — accept or reject it first."""


def refine_skill(
    root: Path,
    slug: str,
    *,
    provider: LLMProvider,
    identity: Identity | None = None,
    hint: str | None = None,
    extra_source: str | None = None,
) -> int:
    """Produce a new iteration via the provider. Returns the new version number."""
    draft = _is_draft(root, slug)
    lineage = _require_lineage(root, slug, draft=draft)

    if any(it.status == "pending" for it in lineage.iterations):
        pending = next(it for it in lineage.iterations if it.status == "pending")
        raise PendingIterationExistsError(
            f"iteration v{pending.version} is pending — "
            f"`forge refine-accept` or `forge refine-reject` it first"
        )

    skill = storage.read_skill(root, slug, identity=identity)
    findings = _latest_judge_findings(root, slug)
    if findings is None:
        raise NoJudgmentToRefineError(
            f"refinement needs an error signal — run `forge judge {slug}` first"
        )

    body = provider.refine(skill, findings=findings, hint=hint, extra_source=extra_source)

    new_version = max(it.version for it in lineage.iterations) + 1
    today = datetime.now(UTC).date()
    storage.write_iteration(
        root,
        slug,
        body=body,
        version=new_version,
        kind="refined",
        created=today,
        draft=draft,
    )

    new_iter = Iteration(
        version=new_version,
        kind="refined",
        created=today,
        judge_score=None,
        status="pending",
    )
    updated = lineage.model_copy(update={"iterations": list(lineage.iterations) + [new_iter]})
    storage.write_lineage(root, slug, updated, draft=draft, overwrite=True)

    append_run_event(
        root,
        RunEvent(
            run_id=next_run_id(root),
            event="refined",
            timestamp=datetime.now(UTC),
            skill_slug=slug,
            promoted=False,
            metadata={"new_version": str(new_version), "hint": hint or ""},
        ),
    )
    return new_version


def accept_iteration(
    root: Path,
    slug: str,
    *,
    version: int,
    identity: Identity | None = None,
) -> Path:
    """Promote `version` to be the current SKILL.md. Re-signs via identity."""
    draft = _is_draft(root, slug)
    lineage = _require_lineage(root, slug, draft=draft)
    target = _find_iteration(lineage, version)
    if target.status not in ("pending", "superseded"):
        raise RefinementError(
            f"iteration v{version} has status {target.status!r}; only 'pending' "
            f"or 'superseded' iterations can be accepted"
        )

    body = storage.read_iteration(root, slug, version, draft=draft)
    current_skill = storage.read_skill(root, slug, identity=identity)
    # Why model_validate not model_copy: model_copy bypasses field validators.
    # The Skill body validator normalizes leading/trailing newlines; without
    # it the body we sign won't match the body we read back (silent sig fail
    # — same class of bug that change #1's body normalizer fixed).
    new_skill = Skill.model_validate(
        {**current_skill.model_dump(mode="json"), "body": body, "signature": None}
    )
    new_path = storage.write_skill(root, new_skill, draft=draft, identity=identity, overwrite=True)

    new_iters: list[Iteration] = []
    for it in lineage.iterations:
        if it.status == "current":
            new_iters.append(it.model_copy(update={"status": "superseded"}))
        elif it.version == version:
            new_iters.append(it.model_copy(update={"status": "current"}))
        else:
            new_iters.append(it)
    updated = Lineage(slug=slug, current_version=version, iterations=new_iters)
    storage.write_lineage(root, slug, updated, draft=draft, overwrite=True)

    append_run_event(
        root,
        RunEvent(
            run_id=next_run_id(root),
            event="promoted",
            timestamp=datetime.now(UTC),
            skill_slug=slug,
            promoted=True,
            metadata={"accepted_iteration": str(version)},
        ),
    )
    return new_path


def reject_iteration(
    root: Path,
    slug: str,
    *,
    version: int,
    reason: str,
) -> None:
    """Mark `version` as rejected. File stays on disk for audit."""
    if not reason or not reason.strip():
        raise ValueError("reject requires a non-empty reason")
    draft = _is_draft(root, slug)
    lineage = _require_lineage(root, slug, draft=draft)
    target = _find_iteration(lineage, version)
    if target.status != "pending":
        raise RefinementError(
            f"iteration v{version} has status {target.status!r}; only 'pending' "
            f"iterations can be rejected"
        )

    new_iters = [
        it.model_copy(update={"status": "rejected", "reject_reason": reason})
        if it.version == version
        else it
        for it in lineage.iterations
    ]
    updated = lineage.model_copy(update={"iterations": new_iters})
    storage.write_lineage(root, slug, updated, draft=draft, overwrite=True)

    append_run_event(
        root,
        RunEvent(
            run_id=next_run_id(root),
            event="demoted",
            timestamp=datetime.now(UTC),
            skill_slug=slug,
            promoted=False,
            metadata={"rejected_iteration": str(version), "reason": reason},
        ),
    )


# --- internals ----------------------------------------------------------------


def _is_draft(root: Path, slug: str) -> bool:
    return not (root / "skills" / slug / "SKILL.md").is_file()


def _require_lineage(root: Path, slug: str, *, draft: bool) -> Lineage:
    try:
        return storage.read_lineage(root, slug, draft=draft)
    except FileNotFoundError as exc:
        raise RefinementError(
            f"{slug!r} has no lineage.yml — run `forge lineage migrate --slug {slug}` first"
        ) from exc


def _find_iteration(lineage: Lineage, version: int) -> Iteration:
    for it in lineage.iterations:
        if it.version == version:
            return it
    raise FileNotFoundError(f"iteration v{version} not in lineage for {lineage.slug!r}")


def _latest_judge_findings(root: Path, slug: str) -> list[JudgeFinding] | None:
    runs_dir = root / "runs"
    if not runs_dir.is_dir():
        return None
    import sys

    for path in sorted(runs_dir.glob("*.jsonl"), reverse=True):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(reversed(lines), start=1):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                print(
                    f"warning: {path.name} line {len(lines) - lineno + 1}: "
                    "could not parse JSON, skipping",
                    file=sys.stderr,
                )
                continue
            if data.get("event") != "judged" or data.get("skill_slug") != slug:
                continue
            findings_raw = data.get("findings", [])
            try:
                return [JudgeFinding(**item) for item in findings_raw]
            except ValidationError as exc:
                print(
                    f"warning: {path.name}: judged event for {slug!r} has "
                    f"invalid findings, skipping: {exc}",
                    file=sys.stderr,
                )
                continue
    return None


def latest_skill(root: Path, slug: str) -> Skill:
    """Helper: load the current SKILL.md regardless of draft/live placement."""
    return storage.read_skill(root, slug)
