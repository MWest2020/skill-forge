"""Filesystem-backed storage adapter.

Specs:
- openspec/changes/add-core-models-and-storage/specs/storage/spec.md
- openspec/changes/add-instance-identity/specs/skill-frontmatter/spec.md

Layout (under {root}):
    skills/{slug}/SKILL.md          live, promoted
    skills/_draft/{slug}/SKILL.md   draft
    sources/{slug}.yml              provenance
    runs/{run_id}.jsonl             pipeline audit (written by change #3)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from skill_forge.identity import (
    Identity,
    SignatureMismatchError,
    sign_skill,
    verify_skill,
)
from skill_forge.models import (
    ITERATION_FILE_RE,
    Lineage,
    Skill,
    SkillEntry,
    SourcesFile,
)


def list_skills(root: Path) -> list[SkillEntry]:
    """Return live + draft skill entries, live first (alpha), then drafts (alpha)."""
    live = _scan(root / "skills", draft=False)
    drafts = _scan(root / "skills" / "_draft", draft=True)
    live.sort(key=lambda e: e.slug)
    drafts.sort(key=lambda e: e.slug)
    return live + drafts


def read_skill(root: Path, slug: str, *, identity: Identity | None = None) -> Skill:
    """Return the Skill for `slug`, preferring live over draft.

    When `identity` is supplied, the loader is **strict**: the skill must
    carry both an `origin` from this instance and a valid `signature`.
    Anything else — missing fields, foreign origin, mismatched signature —
    raises `SignatureMismatchError`. Without an identity argument, no
    verification is performed (status quo for read-only tools like `ls`).

    Strictness defeats the tamper-evidence bypasses that would otherwise
    arise from stripping the signature field or rewriting `origin` to claim
    a foreign instance. Federation (change #8) will introduce a separate
    public-key-lookup path for legitimately-foreign skills.
    """
    live = root / "skills" / slug / "SKILL.md"
    draft = root / "skills" / "_draft" / slug / "SKILL.md"
    for path in (live, draft):
        if path.is_file():
            skill = _read_skill_file(path)
            if identity is not None:
                _verify_strict(skill, slug, path, identity)
            return skill
    raise FileNotFoundError(f"Skill {slug!r} not found. Checked: {live}, {draft}")


def _verify_strict(skill: Skill, slug: str, path: Path, identity: Identity) -> None:
    if skill.origin is None or skill.signature is None:
        raise SignatureMismatchError(
            f"{slug!r} at {path} is unsigned (origin={skill.origin!r}, "
            f"signature={'present' if skill.signature else 'missing'}); "
            f"run `forge identity backfill` to stamp it."
        )
    if not skill.origin.startswith(f"{identity.instance_id}:"):
        raise SignatureMismatchError(
            f"{slug!r} at {path} has foreign origin {skill.origin!r}; "
            f"this instance ({identity.instance_id}) cannot verify it. "
            f"Federation (change #8) is not implemented yet."
        )
    if not verify_skill(skill, identity):
        raise SignatureMismatchError(
            f"signature mismatch for {slug!r} at {path} (origin={skill.origin})"
        )


def read_sources(root: Path, slug: str) -> SourcesFile:
    """Parse `sources/{slug}.yml`."""
    path = root / "sources" / f"{slug}.yml"
    if not path.is_file():
        raise FileNotFoundError(f"No provenance file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SourcesFile(**data)


def write_skill(
    root: Path,
    skill: Skill,
    *,
    draft: bool,
    identity: Identity | None = None,
    overwrite: bool = False,
) -> Path:
    """Write a SKILL.md for `skill`. Returns the path written.

    When `identity` is supplied, missing `origin` and `signature` fields are
    stamped before writing. Skills with both fields already set are written
    as-is (preserves imported / foreign origins).
    """
    base = root / "skills" / "_draft" / skill.name if draft else root / "skills" / skill.name
    base.mkdir(parents=True, exist_ok=True)
    target = base / "SKILL.md"
    if target.exists() and not overwrite:
        raise FileExistsError(f"Skill {skill.name!r} already exists at {target}")
    if identity is not None:
        skill = _stamp(skill, identity)
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
    """Where a Run's JSONL audit log lives (audit module writes it)."""
    return root / "runs" / f"{run_id}.jsonl"


def free_slug(root: Path, base: str) -> str:
    """Find the first slug `base[-N]` that's not in use under skills/ or skills/_draft/."""
    candidate = base
    n = 1
    while _slug_exists_at(root, candidate):
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def _slug_exists_at(root: Path, slug: str) -> bool:
    live = root / "skills" / slug / "SKILL.md"
    draft = root / "skills" / "_draft" / slug / "SKILL.md"
    return live.is_file() or draft.is_file()


def read_skill_file(path: Path) -> Skill:
    """Public helper: parse a SKILL.md at a known path."""
    return _read_skill_file(path)


def parse_skill_text(text: str, path: Path) -> Skill:
    """Parse a SKILL.md from an in-memory string (no second disk read)."""
    frontmatter, body = _split_frontmatter(text, path)
    data: dict[str, Any] = yaml.safe_load(frontmatter) or {}
    data["body"] = body
    return Skill(**data)


# --- iteration storage (change #3) -------------------------------------------


def iterations_dir(root: Path, slug: str, *, draft: bool) -> Path:
    base = root / "skills" / "_draft" / slug if draft else root / "skills" / slug
    return base / "iterations"


def write_iteration(
    root: Path,
    slug: str,
    *,
    body: str,
    version: int,
    kind: str,
    created: date,
    draft: bool,
) -> Path:
    """Write a versioned iteration file. Returns the path."""
    target_dir = iterations_dir(root, slug, draft=draft)
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"v{version}-{kind}-{created.isoformat()}.md"
    path = target_dir / name
    if path.exists():
        raise FileExistsError(f"iteration already exists at {path}")
    rendered = body if body.endswith("\n") else body + "\n"
    path.write_text(rendered, encoding="utf-8")
    return path


def read_iteration(root: Path, slug: str, version: int, *, draft: bool) -> str:
    """Read the body of iteration `version`. Raises if not found / ambiguous."""
    candidates = sorted(
        p for p in iterations_dir(root, slug, draft=draft).glob(f"v{version}-*.md")
        if ITERATION_FILE_RE.match(p.name)
    )
    if not candidates:
        raise FileNotFoundError(
            f"no iteration v{version} for skill {slug!r}"
        )
    if len(candidates) > 1:
        raise ValueError(
            f"multiple iteration files at v{version} for {slug!r}: "
            f"{[p.name for p in candidates]}"
        )
    return candidates[0].read_text(encoding="utf-8")


def read_lineage(root: Path, slug: str, *, draft: bool) -> Lineage:
    path = _lineage_path(root, slug, draft=draft)
    if not path.is_file():
        raise FileNotFoundError(f"no lineage.yml for skill {slug!r} at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Lineage(**data)


def write_lineage(
    root: Path, slug: str, lineage: Lineage, *, draft: bool, overwrite: bool = True
) -> Path:
    path = _lineage_path(root, slug, draft=draft)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"lineage already exists at {path}")
    data = lineage.model_dump(mode="json")
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    return path


def _lineage_path(root: Path, slug: str, *, draft: bool) -> Path:
    base = root / "skills" / "_draft" / slug if draft else root / "skills" / slug
    return base / "lineage.yml"


# --- internals ----------------------------------------------------------------


def _stamp(skill: Skill, identity: Identity) -> Skill:
    """Fill missing `origin` and `signature` for our own skills.

    Foreign-origin skills (origin set but not ours) are returned unchanged.
    Our own skills with both fields already set are returned unchanged.
    When either field is missing, `origin` is regenerated from current
    name+version (avoids origin/version skew if a caller bumped version
    and cleared only the signature) and a fresh signature is computed.
    """
    if skill.origin is not None and not skill.origin.startswith(f"{identity.instance_id}:"):
        return skill  # foreign origin — never re-sign on their behalf
    if skill.origin is not None and skill.signature is not None:
        return skill  # ours and complete
    skill = skill.model_copy(
        update={"origin": f"{identity.instance_id}:{skill.name}:{skill.version}"}
    )
    return skill.model_copy(update={"signature": sign_skill(skill, identity)})


def _scan(directory: Path, *, draft: bool) -> list[SkillEntry]:
    if not directory.is_dir():
        return []
    root = directory.parent.parent if draft else directory.parent
    entries: list[SkillEntry] = []
    for child in directory.iterdir():
        if not child.is_dir() or child.name.startswith("_"):
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            skill = _read_skill_file(skill_md)
        except (ValueError, OSError, yaml.YAMLError):
            continue
        # Prefer the latest RunSummary score over the legacy Skill.judge_score.
        # Why `is not None`: a legit judge score of exactly 0.0 is falsy and
        # would otherwise fall through to the (also-falsy) legacy field.
        from_runs = _latest_run_score(root, child.name)
        score = from_runs if from_runs is not None else skill.judge_score
        entries.append(SkillEntry(slug=child.name, draft=draft, judge_score=score))
    return entries


def _latest_run_score(root: Path, slug: str) -> float | None:
    path = root / "sources" / f"{slug}.yml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        sources = SourcesFile(**data)
    except (ValueError, OSError, yaml.YAMLError):
        return None
    if not sources.runs:
        return None
    return sources.runs[-1].judge_score


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
    """Inverse of _split_frontmatter — frontmatter YAML + body.

    Frontmatter is dumped with `sort_keys=True` so the canonical payload that
    signatures cover is reproducible across writes.
    """
    fm_data = skill.model_dump(mode="json", exclude={"body"})
    fm_yaml = yaml.safe_dump(fm_data, sort_keys=True, default_flow_style=False)
    body = skill.body
    if not body.endswith("\n"):
        body += "\n"
    return f"---\n{fm_yaml}---\n\n{body}"
