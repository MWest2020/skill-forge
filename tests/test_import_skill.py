"""Tests for skill_forge.import_skill — change #2 add-import-and-judge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_forge.identity import from_seed
from skill_forge.import_skill import (
    SkillImportError,
    SkillImportErrorGroup,
    import_directory,
    import_file,
)
from skill_forge.storage import filesystem as fs

_SEED = b"\x11" * 32

_VALID_SKILL_MD = """\
---
created: '2026-05-24'
description: Use this skill when X.
judge_score: null
name: imported-skill
sources:
- id: src-aaaaaa
version: 1
---

## When to use
...

## Procedure
...

## Failure modes
...
"""


def _write_skill_md(path: Path, body: str = _VALID_SKILL_MD) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# --- import_file --------------------------------------------------------------


def test_import_file_writes_draft_and_sources(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    src = _write_skill_md(tmp_path / "incoming" / "skill.md")
    identity = from_seed(tmp_path / "id", _SEED)

    skill, sources = import_file(root, src, identity=identity)

    assert (root / "skills" / "_draft" / "imported-skill" / "SKILL.md").is_file()
    assert (root / "sources" / "imported-skill.yml").is_file()
    assert skill.name == "imported-skill"
    # `skill` is the parsed in-memory record; the on-disk version is stamped.
    on_disk = fs.read_skill(root, "imported-skill", identity=identity)
    assert on_disk.origin == f"{identity.instance_id}:imported-skill:1"
    assert on_disk.signature is not None
    assert len(sources) == 1
    assert sources[0].url.startswith("local-author:")
    assert sources[0].contribution == "imported from manual"


def test_import_file_origin_tag_annotates_contribution(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    src = _write_skill_md(tmp_path / "in" / "s.md")
    _, sources = import_file(root, src, origin_tag="external/claude-code")
    assert sources[0].contribution == "imported from external/claude-code"


def test_import_file_rejects_invalid_frontmatter(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    src = _write_skill_md(tmp_path / "in" / "bad.md", body="no frontmatter at all\n")
    with pytest.raises(SkillImportError):
        import_file(root, src)
    # Nothing should have landed.
    assert not (root / "skills").exists() or not any((root / "skills").rglob("SKILL.md"))


def test_import_file_missing_path(tmp_path: Path) -> None:
    with pytest.raises(SkillImportError, match="not found"):
        import_file(tmp_path / "repo", tmp_path / "ghost.md")


def test_import_file_auto_suffixes_on_collision(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    src = _write_skill_md(tmp_path / "in" / "s.md")
    identity = from_seed(tmp_path / "id", _SEED)

    import_file(root, src, identity=identity)
    skill_two, _ = import_file(root, src, identity=identity)

    assert skill_two.name == "imported-skill-2"
    assert (root / "skills" / "_draft" / "imported-skill-2" / "SKILL.md").is_file()


def test_import_file_appends_audit_event(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    src = _write_skill_md(tmp_path / "in" / "s.md")
    import_file(root, src)

    run_files = sorted((root / "runs").glob("*.jsonl"))
    assert len(run_files) == 1
    line = run_files[0].read_text(encoding="utf-8").splitlines()[0]
    event = json.loads(line)
    assert event["event"] == "imported"
    assert event["skill_slug"] == "imported-skill"


def test_import_file_foreign_origin_preserved(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    foreign = "forge-deadbeef:imported-skill:1"
    foreign_md = _VALID_SKILL_MD.replace("version: 1\n", f"origin: {foreign}\nversion: 1\n")
    src = _write_skill_md(tmp_path / "in" / "s.md", body=foreign_md)
    identity = from_seed(tmp_path / "id", _SEED)

    skill, sources = import_file(root, src, identity=identity)
    assert skill.origin == foreign
    assert sources[0].url == f"external:{foreign}"


# --- import_directory --------------------------------------------------------


def test_import_directory_picks_up_subdir_skills(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    src_root = tmp_path / "library"
    _write_skill_md(
        src_root / "skill-a" / "SKILL.md",
        body=_VALID_SKILL_MD.replace("imported-skill", "skill-a"),
    )
    _write_skill_md(
        src_root / "skill-b" / "SKILL.md",
        body=_VALID_SKILL_MD.replace("imported-skill", "skill-b"),
    )
    (src_root / "not-a-skill" / "README.md").parent.mkdir(parents=True)
    (src_root / "not-a-skill" / "README.md").write_text("nothing here", encoding="utf-8")

    results = import_directory(root, src_root)
    names = sorted(s.name for s, _ in results)
    assert names == ["skill-a", "skill-b"]


def test_import_directory_groups_failures(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    src_root = tmp_path / "library"
    _write_skill_md(
        src_root / "good" / "SKILL.md",
        body=_VALID_SKILL_MD.replace("imported-skill", "good-skill"),
    )
    _write_skill_md(src_root / "bad" / "SKILL.md", body="malformed garbage\n")

    with pytest.raises(SkillImportErrorGroup) as exc:
        import_directory(root, src_root)
    assert len(exc.value.failures) == 1
    # The good one still landed despite the bad one failing.
    assert (root / "skills" / "_draft" / "good-skill" / "SKILL.md").is_file()


def test_import_directory_shares_run_id_for_bulk(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    src_root = tmp_path / "library"
    _write_skill_md(
        src_root / "a" / "SKILL.md",
        body=_VALID_SKILL_MD.replace("imported-skill", "a-skill"),
    )
    _write_skill_md(
        src_root / "b" / "SKILL.md",
        body=_VALID_SKILL_MD.replace("imported-skill", "b-skill"),
    )
    import_directory(root, src_root)

    run_files = sorted((root / "runs").glob("*.jsonl"))
    assert len(run_files) == 1  # one shared run_id
    lines = run_files[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # one event per imported skill
