"""Tests for Iteration/Lineage models + storage helpers + migrate."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from skill_forge.cli import app
from skill_forge.lineage import migrate_all, migrate_one
from skill_forge.models import (
    Iteration,
    Lineage,
    Skill,
    SourceRef,
)
from skill_forge.storage import filesystem as fs

runner = CliRunner()


def _iter(version: int = 1, status: str = "current", **extra: object) -> Iteration:
    base: dict[str, object] = dict(
        version=version,
        kind="imported",
        created=date(2026, 5, 24),
        status=status,
    )
    base.update(extra)
    return Iteration(**base)  # type: ignore[arg-type]


def _skill(name: str = "demo") -> Skill:
    return Skill(
        name=name,
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="# Body\n",
    )


# --- Iteration model ----------------------------------------------------------


def test_iteration_round_trip() -> None:
    it = _iter()
    assert Iteration(**it.model_dump(mode="json")) == it


def test_iteration_rejects_bad_kind() -> None:
    with pytest.raises(ValidationError):
        _iter(kind="something-else")


def test_iteration_rejects_bad_status() -> None:
    with pytest.raises(ValidationError):
        _iter(status="approved")


def test_iteration_reject_reason_required_when_rejected() -> None:
    with pytest.raises(ValidationError):
        _iter(status="rejected", reject_reason=None)
    _iter(status="rejected", reject_reason="too short")


def test_iteration_reject_reason_forbidden_unless_rejected() -> None:
    with pytest.raises(ValidationError):
        _iter(status="current", reject_reason="why?")


# --- Lineage model ------------------------------------------------------------


def test_lineage_round_trip() -> None:
    line = Lineage(
        slug="demo",
        current_version=1,
        iterations=[_iter()],
    )
    assert Lineage(**line.model_dump(mode="json")) == line


def test_lineage_requires_exactly_one_current() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        Lineage(
            slug="demo",
            current_version=1,
            iterations=[_iter(1, "current"), _iter(2, "current")],
        )
    with pytest.raises(ValidationError, match="exactly one"):
        Lineage(
            slug="demo",
            current_version=1,
            iterations=[_iter(1, "superseded")],
        )


def test_lineage_current_version_must_match() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        Lineage(
            slug="demo",
            current_version=2,  # but iteration is version 1
            iterations=[_iter(1, "current")],
        )


def test_lineage_versions_monotonic() -> None:
    with pytest.raises(ValidationError, match="monotonic"):
        Lineage(
            slug="demo",
            current_version=1,
            iterations=[
                _iter(2, "superseded"),
                _iter(1, "current"),
            ],
        )


# --- Storage helpers ----------------------------------------------------------


def test_write_iteration_creates_file(tmp_path: Path) -> None:
    path = fs.write_iteration(
        tmp_path,
        "demo",
        body="hello world",
        version=1,
        kind="refined",
        created=date(2026, 5, 24),
        draft=False,
    )
    assert path.name == "v1-refined-2026-05-24.md"
    assert path.is_file()
    assert path.read_text() == "hello world\n"


def test_write_iteration_refuses_collision(tmp_path: Path) -> None:
    fs.write_iteration(
        tmp_path,
        "demo",
        body="a",
        version=1,
        kind="imported",
        created=date(2026, 5, 24),
        draft=False,
    )
    with pytest.raises(FileExistsError):
        fs.write_iteration(
            tmp_path,
            "demo",
            body="b",
            version=1,
            kind="imported",
            created=date(2026, 5, 24),
            draft=False,
        )


def test_read_iteration_returns_body(tmp_path: Path) -> None:
    fs.write_iteration(
        tmp_path,
        "demo",
        body="hello\n",
        version=2,
        kind="refined",
        created=date(2026, 5, 24),
        draft=False,
    )
    assert fs.read_iteration(tmp_path, "demo", 2, draft=False) == "hello\n"


def test_read_iteration_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        fs.read_iteration(tmp_path, "demo", 99, draft=False)


def test_lineage_write_read_round_trip(tmp_path: Path) -> None:
    line = Lineage(slug="demo", current_version=1, iterations=[_iter()])
    fs.write_lineage(tmp_path, "demo", line, draft=False)
    assert fs.read_lineage(tmp_path, "demo", draft=False) == line


# --- Migration ----------------------------------------------------------------


def test_migrate_one_flat_skill(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)
    assert migrate_one(tmp_path, "demo", draft=False) is True
    line = fs.read_lineage(tmp_path, "demo", draft=False)
    assert line.current_version == 1
    assert line.iterations[0].kind == "imported"
    assert line.iterations[0].status == "current"
    # v1 file holds the body (no frontmatter) so refine/accept can swap
    # bodies in/out without touching frontmatter.
    iters = list(fs.iterations_dir(tmp_path, "demo", draft=False).glob("v1-*.md"))
    assert len(iters) == 1
    assert iters[0].read_text() == _skill().body
    # Frontmatter delimiter stays out of iteration files
    assert "---" not in iters[0].read_text()


def test_migrate_one_is_idempotent(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)
    assert migrate_one(tmp_path, "demo", draft=False) is True
    assert migrate_one(tmp_path, "demo", draft=False) is False  # already done


def test_migrate_one_skips_missing_skill(tmp_path: Path) -> None:
    assert migrate_one(tmp_path, "ghost", draft=False) is False


def test_migrate_all_walks_live_and_draft(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("live-one"), draft=False)
    fs.write_skill(tmp_path, _skill("draft-one"), draft=True)
    migrated = migrate_all(tmp_path)
    assert sorted(migrated) == sorted([("live-one", False), ("draft-one", True)])
    # Second run finds nothing
    assert migrate_all(tmp_path) == []


def test_migrate_dry_run_writes_nothing(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)
    migrate_one(tmp_path, "demo", draft=False, dry_run=True)
    # No lineage.yml, no iterations/ — just the original SKILL.md
    assert not (tmp_path / "skills" / "demo" / "lineage.yml").exists()
    assert not (tmp_path / "skills" / "demo" / "iterations").exists()


# --- CLI ----------------------------------------------------------------------


def test_cli_lineage_migrate_all(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("a"), draft=False)
    fs.write_skill(tmp_path, _skill("b"), draft=True)
    result = runner.invoke(app, ["lineage", "migrate", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "migrated:" in result.output
    assert "2 skill(s)" in result.output


def test_cli_lineage_migrate_single_slug(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("a"), draft=False)
    fs.write_skill(tmp_path, _skill("b"), draft=False)
    result = runner.invoke(app, ["lineage", "migrate", "--slug", "a", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "migrated: skills/a" in result.output
    # b is untouched
    assert not (tmp_path / "skills" / "b" / "lineage.yml").exists()


def test_cli_lineage_migrate_dry_run(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)
    result = runner.invoke(app, ["lineage", "migrate", "--dry-run", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "would migrate:" in result.output
    assert not (tmp_path / "skills" / "demo" / "lineage.yml").exists()
