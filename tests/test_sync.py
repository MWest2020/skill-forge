"""Tests for forge sync — change #6 add-plugin-bridges."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skill_forge.cli import app
from skill_forge.models import Skill, SourceRef
from skill_forge.storage import filesystem as fs
from skill_forge.sync import (
    SyncError,
    sync_target,
    unsync_target,
)
from skill_forge.sync.sync import _read_manifest

runner = CliRunner()


def _skill(name: str = "demo") -> Skill:
    return Skill(
        name=name,
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="# Body\n",
    )


def _seed_promoted(tmp_path: Path, slug: str = "demo") -> None:
    fs.write_skill(tmp_path, _skill(slug), draft=False)


# --- sync_target -------------------------------------------------------------


def test_sync_creates_symlinks(tmp_path: Path) -> None:
    _seed_promoted(tmp_path, "alpha")
    _seed_promoted(tmp_path, "beta")
    target_dir = tmp_path / "out"
    manifest = sync_target(tmp_path, target="claude-code", target_dir=target_dir, mode="symlink")
    assert len(manifest.entries) == 2
    a = target_dir / "alpha" / "SKILL.md"
    b = target_dir / "beta" / "SKILL.md"
    assert a.is_symlink() and a.resolve() == (tmp_path / "skills" / "alpha" / "SKILL.md").resolve()
    assert b.is_symlink()


def test_sync_creates_copies_in_copy_mode(tmp_path: Path) -> None:
    _seed_promoted(tmp_path)
    target_dir = tmp_path / "out"
    sync_target(tmp_path, target="claude-code", target_dir=target_dir, mode="copy")
    placed = target_dir / "demo" / "SKILL.md"
    assert placed.is_file() and not placed.is_symlink()


def test_sync_unknown_target(tmp_path: Path) -> None:
    with pytest.raises(SyncError, match="unknown target"):
        sync_target(tmp_path, target="emacs", target_dir=tmp_path / "out")


def test_sync_refuses_home_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Make Path.home() resolve to tmp_path so we don't actually touch real home
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    _seed_promoted(tmp_path)
    with pytest.raises(SyncError, match="home directory"):
        sync_target(tmp_path, target="claude-code", target_dir=tmp_path, mode="copy")


def test_sync_writes_manifest(tmp_path: Path) -> None:
    _seed_promoted(tmp_path)
    target_dir = tmp_path / "out"
    sync_target(tmp_path, target="claude-code", target_dir=target_dir, mode="symlink")
    manifest = _read_manifest(tmp_path, "claude-code")
    assert manifest is not None
    assert manifest.target == "claude-code"
    assert len(manifest.entries) == 1


def test_sync_re_run_replaces_existing(tmp_path: Path) -> None:
    _seed_promoted(tmp_path)
    target_dir = tmp_path / "out"
    sync_target(tmp_path, target="claude-code", target_dir=target_dir, mode="symlink")
    # Run again — should replace, not error
    sync_target(tmp_path, target="claude-code", target_dir=target_dir, mode="symlink")
    placed = target_dir / "demo" / "SKILL.md"
    assert placed.is_symlink()


def test_sync_only_promoted_not_drafts(tmp_path: Path) -> None:
    _seed_promoted(tmp_path, "live-one")
    fs.write_skill(tmp_path, _skill("draft-one"), draft=True)
    target_dir = tmp_path / "out"
    manifest = sync_target(tmp_path, target="claude-code", target_dir=target_dir, mode="copy")
    slugs = {e.slug for e in manifest.entries}
    assert slugs == {"live-one"}


# --- unsync_target -----------------------------------------------------------


def test_unsync_removes_synced_files(tmp_path: Path) -> None:
    _seed_promoted(tmp_path)
    target_dir = tmp_path / "out"
    sync_target(tmp_path, target="claude-code", target_dir=target_dir, mode="symlink")
    removed, expected = unsync_target(tmp_path, target="claude-code")
    assert (removed, expected) == (1, 1)
    assert not (target_dir / "demo" / "SKILL.md").exists()
    assert not (target_dir / "demo").exists()
    assert not (tmp_path / "sync" / "claude-code.yml").exists()


def test_unsync_tolerates_missing_files(tmp_path: Path) -> None:
    _seed_promoted(tmp_path)
    target_dir = tmp_path / "out"
    sync_target(tmp_path, target="claude-code", target_dir=target_dir, mode="copy")
    (target_dir / "demo" / "SKILL.md").unlink()
    removed, expected = unsync_target(tmp_path, target="claude-code")
    assert removed == 0
    assert expected == 1  # the manifest still expected one


def test_unsync_no_manifest_returns_zero(tmp_path: Path) -> None:
    assert unsync_target(tmp_path, target="claude-code") == (0, 0)


def test_sync_refuses_system_dirs(tmp_path: Path) -> None:
    _seed_promoted(tmp_path)
    for path in (Path("/etc"), Path("/usr")):
        with pytest.raises(SyncError, match="system directory"):
            sync_target(tmp_path, target="claude-code", target_dir=path, mode="copy")


# --- sync --tag (skillsets) --------------------------------------------------


def _seed_tagged(tmp_path: Path, slug: str, tags: list[str]) -> None:
    fs.write_skill(tmp_path, _skill(slug).model_copy(update={"tags": tags}), draft=False)


def test_sync_tag_mounts_only_skillset(tmp_path: Path) -> None:
    _seed_tagged(tmp_path, "sec", ["security"])
    _seed_tagged(tmp_path, "web", ["web"])
    target_dir = tmp_path / "out"
    manifest = sync_target(
        tmp_path, target="claude-code", target_dir=target_dir, mode="copy", tag="security"
    )
    assert {e.slug for e in manifest.entries} == {"sec"}
    assert (target_dir / "sec" / "SKILL.md").is_file()
    assert not (target_dir / "web").exists()


def test_sync_tag_empty_skillset_raises(tmp_path: Path) -> None:
    _seed_tagged(tmp_path, "sec", ["security"])
    with pytest.raises(SyncError, match="no live skills tagged"):
        sync_target(
            tmp_path, target="claude-code", target_dir=tmp_path / "out", mode="copy", tag="nope"
        )


def test_unsync_tag_keeps_other_entries(tmp_path: Path) -> None:
    _seed_tagged(tmp_path, "sec", ["security"])
    _seed_tagged(tmp_path, "web", ["web"])
    target_dir = tmp_path / "out"
    sync_target(tmp_path, target="claude-code", target_dir=target_dir, mode="copy")  # both
    removed, expected = unsync_target(tmp_path, target="claude-code", tag="security")
    assert (removed, expected) == (1, 1)
    assert not (target_dir / "sec").exists()
    assert (target_dir / "web" / "SKILL.md").is_file()
    manifest = _read_manifest(tmp_path, "claude-code")
    assert manifest is not None
    assert {e.slug for e in manifest.entries} == {"web"}


def test_sync_cli_tag_empty_exits_1(tmp_path: Path) -> None:
    _seed_tagged(tmp_path, "sec", ["security"])
    result = runner.invoke(
        app,
        ["sync", "claude-code", "--tag", "nope", "--target-dir", str(tmp_path / "out")],
    )
    assert result.exit_code == 1
    assert "no live skills tagged" in (result.stderr or result.output)


def test_sync_refuses_home_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A typo like --target-dir / on macOS shouldn't smash /Users either."""
    fake_home = tmp_path / "fake-home" / "user"
    fake_home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    _seed_promoted(tmp_path)
    with pytest.raises(SyncError, match="parent of your home"):
        sync_target(
            tmp_path,
            target="claude-code",
            target_dir=tmp_path / "fake-home",
            mode="copy",
        )


# --- CLI ---------------------------------------------------------------------


def test_cli_sync(tmp_path: Path) -> None:
    _seed_promoted(tmp_path)
    target_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "sync",
            "claude-code",
            "--target-dir",
            str(target_dir),
            "--mode",
            "copy",
            "--root",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Synced: 1 skill(s)" in result.output


def test_cli_sync_unsync(tmp_path: Path) -> None:
    _seed_promoted(tmp_path)
    target_dir = tmp_path / "out"
    runner.invoke(
        app,
        [
            "sync",
            "claude-code",
            "--target-dir",
            str(target_dir),
            "--mode",
            "copy",
            "--root",
            str(tmp_path),
        ],
    )
    result = runner.invoke(app, ["sync", "claude-code", "--unsync", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "Unsynced" in result.output


def test_cli_sync_unknown_target(tmp_path: Path) -> None:
    result = runner.invoke(app, ["sync", "emacs", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "unknown target" in (result.stderr or result.output)
