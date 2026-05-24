"""Tests for skill_forge.config — change #2.1."""

from __future__ import annotations

from pathlib import Path

from skill_forge.config import DEFAULTS, load


def test_load_returns_defaults_when_no_file(tmp_path: Path) -> None:
    cfg = load(tmp_path)
    assert cfg["providers"]["extract"] == DEFAULTS["providers"]["extract"]
    assert cfg["anthropic"]["model"] == "claude-opus-4-7"


def test_load_overlays_project_file(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "default.yml").write_text(
        "providers:\n  extract: anthropic\nanthropic:\n  model: claude-sonnet-4-6\n",
        encoding="utf-8",
    )
    cfg = load(tmp_path)
    assert cfg["providers"]["extract"] == "anthropic"
    assert cfg["providers"]["judge"] == DEFAULTS["providers"]["judge"]  # unchanged
    assert cfg["anthropic"]["model"] == "claude-sonnet-4-6"
    assert cfg["anthropic"]["max_tokens"] == 4096  # bundled default preserved


def test_load_returns_defaults_when_yaml_is_empty(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "default.yml").write_text("", encoding="utf-8")
    cfg = load(tmp_path)
    assert cfg == DEFAULTS


def test_load_returns_defaults_when_yaml_is_not_a_dict(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "default.yml").write_text("- just a list\n", encoding="utf-8")
    cfg = load(tmp_path)
    assert cfg == DEFAULTS


def test_defaults_are_not_mutated_by_load(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "default.yml").write_text("providers:\n  extract: anthropic\n", encoding="utf-8")
    load(tmp_path)
    assert DEFAULTS["providers"]["extract"] == "claude_code"
