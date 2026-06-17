"""Append-only audit trail for pipeline actions.

Spec: openspec/changes/add-import-and-judge/specs/audit-trail/spec.md
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from skill_forge.models import CalibrationRecord, RunEvent

_RUN_FILE_RE = re.compile(r"^run-(\d{4}-\d{2}-\d{2})-(\d{3})\.jsonl$")
_CALIBRATION_EVENT = "calibrated"


def next_run_id(root: Path, *, now: datetime | None = None) -> str:
    """Compute the next `run-YYYY-MM-DD-NNN` for `runs/` under root.

    Scans existing files; takes the max counter for today + 1, or 001.
    """
    today = (now or datetime.now(UTC)).strftime("%Y-%m-%d")
    runs_dir = root / "runs"
    if not runs_dir.is_dir():
        return f"run-{today}-001"
    max_n = 0
    for entry in runs_dir.iterdir():
        m = _RUN_FILE_RE.match(entry.name)
        if not m or m.group(1) != today:
            continue
        n = int(m.group(2))
        if n > max_n:
            max_n = n
    return f"run-{today}-{max_n + 1:03d}"


def append_run_event(root: Path, event: RunEvent) -> Path:
    """Append one JSONL line to `runs/{event.run_id}.jsonl`. Returns the path."""
    runs_dir = root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{event.run_id}.jsonl"
    payload = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(payload + "\n")
    return path


def append_calibration(
    root: Path, record: CalibrationRecord, *, now: datetime | None = None
) -> Path:
    """Record a calibration result to the audit trail. It gets its own run id
    and file; the line carries an `event: "calibrated"` discriminator so
    `latest_event` (which parses RunEvents) safely skips it."""
    run_id = next_run_id(root, now=now)
    runs_dir = root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{run_id}.jsonl"
    line = {
        "event": _CALIBRATION_EVENT,
        "run_id": run_id,
        "record": record.model_dump(mode="json"),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, separators=(",", ":")) + "\n")
    return path


def latest_calibration(root: Path, *, passing: bool = False) -> CalibrationRecord | None:
    """The most recent calibration record (by run id), or None. With
    `passing=True`, only consider records whose `passed` is true."""
    runs_dir = root / "runs"
    if not runs_dir.is_dir():
        return None
    best_id: str | None = None
    best: CalibrationRecord | None = None
    for path in sorted(runs_dir.glob("run-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict) or obj.get("event") != _CALIBRATION_EVENT:
                continue
            try:
                record = CalibrationRecord.model_validate(obj["record"])
            except (ValueError, KeyError):
                continue
            if passing and not record.passed:
                continue
            run_id = str(obj.get("run_id", ""))
            if best is None or run_id >= best_id:  # type: ignore[operator]
                best_id, best = run_id, record
    return best


def latest_event(root: Path, slug: str, event: str) -> RunEvent | None:
    """The most recent `event`-kind RunEvent for `slug`, or None.

    Scans `runs/*.jsonl` (the audit trail is the source of truth) and returns
    the highest-`run_id` match — run ids are date+counter, so lexical max is
    chronological. Unparseable lines are skipped, not fatal.
    """
    runs_dir = root / "runs"
    if not runs_dir.is_dir():
        return None
    best: RunEvent | None = None
    for path in sorted(runs_dir.glob("run-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                candidate = RunEvent.model_validate_json(line)
            except ValueError:
                continue
            if candidate.event != event or candidate.skill_slug != slug:
                continue
            if best is None or candidate.run_id >= best.run_id:
                best = candidate
    return best
