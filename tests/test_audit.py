"""Tests for skill_forge.audit — change #2 add-import-and-judge."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.models import RunEvent

_NOW = datetime(2026, 5, 24, 14, 30, tzinfo=UTC)


def _event(run_id: str = "run-2026-05-24-001", event: str = "imported") -> RunEvent:
    return RunEvent(
        run_id=run_id,
        event=event,
        timestamp=_NOW,
        skill_slug="demo-skill",
    )


# --- next_run_id --------------------------------------------------------------


def test_next_run_id_starts_at_001(tmp_path: Path) -> None:
    assert next_run_id(tmp_path, now=_NOW) == "run-2026-05-24-001"


def test_next_run_id_increments(tmp_path: Path) -> None:
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "run-2026-05-24-001.jsonl").touch()
    (tmp_path / "runs" / "run-2026-05-24-002.jsonl").touch()
    assert next_run_id(tmp_path, now=_NOW) == "run-2026-05-24-003"


def test_next_run_id_ignores_other_dates(tmp_path: Path) -> None:
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "run-2026-05-23-099.jsonl").touch()
    assert next_run_id(tmp_path, now=_NOW) == "run-2026-05-24-001"


def test_next_run_id_ignores_bad_filenames(tmp_path: Path) -> None:
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "not-a-run.jsonl").touch()
    (tmp_path / "runs" / "run-2026-05-24-001.jsonl").touch()
    assert next_run_id(tmp_path, now=_NOW) == "run-2026-05-24-002"


# --- append_run_event ---------------------------------------------------------


def test_append_run_event_creates_runs_dir_and_writes_line(tmp_path: Path) -> None:
    path = append_run_event(tmp_path, _event())
    assert path == tmp_path / "runs" / "run-2026-05-24-001.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["event"] == "imported"
    assert parsed["skill_slug"] == "demo-skill"
    assert parsed["run_id"] == "run-2026-05-24-001"


def test_append_run_event_appends_to_existing_file(tmp_path: Path) -> None:
    append_run_event(tmp_path, _event(event="imported"))
    append_run_event(tmp_path, _event(event="judged"))
    path = tmp_path / "runs" / "run-2026-05-24-001.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "imported"
    assert json.loads(lines[1])["event"] == "judged"


def test_run_event_rejects_bad_event_name() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RunEvent(
            run_id="run-2026-05-24-001",
            event="exploded",
            timestamp=_NOW,
            skill_slug="demo",
        )
