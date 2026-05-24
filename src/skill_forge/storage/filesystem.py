"""Filesystem-backed storage adapter.

Specs: openspec/changes/add-core-models-and-storage/specs/storage/spec.md

Layout (under {root}):
    skills/{slug}/SKILL.md          live, promoted
    skills/_draft/{slug}/SKILL.md   draft
    sources/{slug}.yml              provenance
    runs/{run_id}.jsonl             pipeline audit (written by change #3)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from skill_forge.models import Skill, SkillEntry, SourcesFile


def list_skills(root: Path) -> list[SkillEntry]:
    """Return live + draft skill entries, live first (alpha), then drafts (alpha)."""
    live = _scan(root / "skills", draft=False)
    drafts = _scan(root / "skills" / "_draft", draft=True)
    live.sort(key=lambda e: e.slug)
    drafts.sort(key=lambda e: e.slug)
    return live + drafts


def read_skill(root: Path, slug: str) -> Skill:
    """Return the Skill for `slug`, preferring live over draft."""
    live = root / "skills" / slug / "SKILL.md"
    draft = root / "skills" / "_draft" / slug / "SKILL.md"
    for path in (live, draft):
        if path.is_file():
            return _read_skill_file(path)
    raise FileNotFoundError(f"Skill {slug!r} not found. Checked: {live}, {draft}")


def read_sources(root: Path, slug: str) -> SourcesFile:
    """Parse `sources/{slug}.yml`."""
    path = root / "sources" / f"{slug}.yml"
    if not path.is_file():
        raise FileNotFoundError(f"No provenance file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SourcesFile(**data)


def write_skill(root: Path, skill: Skill, *, draft: bool, overwrite: bool = False) -> Path:
    """Write a SKILL.md for `skill`. Returns the path written."""
    base = root / "skills" / "_draft" / skill.name if draft else root / "skills" / skill.name
    base.mkdir(parents=True, exist_ok=True)
    target = base / "SKILL.md"
    if target.exists() and not overwrite:
        raise FileExistsError(f"Skill {skill.name!r} already exists at {target}")
    target.write_text(_render_skill(skill), encoding="utf-8")
    return target


def write_sources(
    root: Path, slug: str, sources_file: SourcesFile, *, overwrite: bool = False
) -> Path:
    """Write `sources/{slug}.yml`. Returns the path written."""
    target = root / "sources" / f"{slug}.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Sources file already exists at {target}")
    data = sources_file.model_dump(mode="json")
    target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return target


def runs_path(root: Path, run_id: str) -> Path:
    """Where a Run's JSONL audit log lives (writing lands in change #3)."""
    return root / "runs" / f"{run_id}.jsonl"


# --- internals ----------------------------------------------------------------


def _scan(directory: Path, *, draft: bool) -> list[SkillEntry]:
    if not directory.is_dir():
        return []
    entries: list[SkillEntry] = []
    for child in directory.iterdir():
        if not child.is_dir() or child.name.startswith("_"):
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            skill = _read_skill_file(skill_md)
        except (ValueError, OSError):
            continue
        entries.append(SkillEntry(slug=child.name, draft=draft, judge_score=skill.judge_score))
    return entries


def _read_skill_file(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text, path)
    data: dict[str, Any] = yaml.safe_load(frontmatter) or {}
    data["body"] = body
    return Skill(**data)


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    start = _first_nonempty(lines)
    if start is None or lines[start].strip() != "---":
        raise ValueError(f"{path}: frontmatter delimiter '---' must be the first non-empty line")
    end = _find_closing(lines, start + 1)
    if end is None:
        raise ValueError(f"{path}: closing frontmatter delimiter '---' not found")
    frontmatter = "".join(lines[start + 1 : end])
    body = "".join(lines[end + 1 :]).lstrip("\n")
    return frontmatter, body


def _first_nonempty(lines: list[str]) -> int | None:
    for i, line in enumerate(lines):
        if line.strip() != "":
            return i
    return None


def _find_closing(lines: list[str], start: int) -> int | None:
    for i in range(start, len(lines)):
        if lines[i].rstrip() == "---":
            return i
    return None


def _render_skill(skill: Skill) -> str:
    """Inverse of _split_frontmatter — frontmatter YAML + body."""
    fm_data = skill.model_dump(mode="json", exclude={"body"})
    fm_yaml = yaml.safe_dump(fm_data, sort_keys=False)
    body = skill.body
    if not body.endswith("\n"):
        body += "\n"
    return f"---\n{fm_yaml}---\n\n{body}"
