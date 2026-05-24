"""Append-only audit trail for pipeline actions.

Spec: openspec/changes/add-import-and-judge/specs/audit-trail/spec.md
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from skill_forge.models import RunEvent

_RUN_FILE_RE = re.compile(r"^run-(\d{4}-\d{2}-\d{2})-(\d{3})\.jsonl$")


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
