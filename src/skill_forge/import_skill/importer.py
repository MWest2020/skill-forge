"""Import an existing SKILL.md into the library.

Spec: openspec/changes/add-import-and-judge/specs/import/spec.md
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.identity import Identity
from skill_forge.import_skill.normalize import normalize_skill_md
from skill_forge.models import RunEvent, Skill, Source, SourcesFile
from skill_forge.storage import filesystem as storage


class SkillImportError(Exception):
    """One importable file failed to parse, validate, or write."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class SkillImportErrorGroup(Exception):  # noqa: N818  # "ErrorGroup" reads better than "GroupError"
    """Partial-success report from `import_directory`."""

    def __init__(self, failures: list[SkillImportError]) -> None:
        super().__init__(f"{len(failures)} import(s) failed")
        self.failures = failures


def import_file(
    root: Path,
    path: Path,
    *,
    identity: Identity | None = None,
    origin_tag: str | None = None,
    run_id: str | None = None,
) -> tuple[Skill, list[Source]]:
    """Import one SKILL.md file into `{root}/skills/_draft/{slug}/`."""
    if not path.is_file():
        raise SkillImportError(path, "file not found")
    # Read once, parse from memory — avoids a TOCTOU window where the file
    # bytes (which we sha256) drift from the bytes we parsed.
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SkillImportError(path, str(exc)) from exc
    try:
        text = normalize_skill_md(raw.decode("utf-8", errors="replace"))
        parsed = storage.parse_skill_text(text, path)
    except (ValueError, ValidationError) as exc:
        raise SkillImportError(path, str(exc)) from exc

    sha256 = hashlib.sha256(raw).hexdigest()
    slug = storage.free_slug(root, parsed.name)
    if slug != parsed.name:
        parsed = parsed.model_copy(update={"name": slug})

    source = _build_source(parsed, identity, sha256, origin_tag)
    sources_file = SourcesFile(slug=slug, sources=[source], runs=[])

    storage.write_skill(root, parsed, draft=True, identity=identity)
    storage.write_sources(root, slug, sources_file)

    event = RunEvent(
        run_id=run_id or next_run_id(root),
        event="imported",
        timestamp=datetime.now(UTC),
        skill_slug=slug,
        metadata={"source_path": str(path), "origin_tag": origin_tag or ""},
    )
    append_run_event(root, event)

    return parsed, [source]


def import_directory(
    root: Path,
    src_dir: Path,
    *,
    identity: Identity | None = None,
    origin_tag: str | None = None,
) -> list[tuple[Skill, list[Source]]]:
    """Import every subdirectory of `src_dir` that contains a SKILL.md."""
    if not src_dir.is_dir():
        raise SkillImportError(src_dir, "directory not found")
    results: list[tuple[Skill, list[Source]]] = []
    failures: list[SkillImportError] = []
    run_id = next_run_id(root)  # one run_id for the whole bulk import
    for child in sorted(src_dir.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            result = import_file(
                root,
                skill_md,
                identity=identity,
                origin_tag=origin_tag,
                run_id=run_id,
            )
        except SkillImportError as exc:
            failures.append(exc)
            continue
        results.append(result)
    if failures:
        raise SkillImportErrorGroup(failures)
    return results


def _build_source(
    parsed: Skill,
    identity: Identity | None,
    sha256: str,
    origin_tag: str | None,
) -> Source:
    now = datetime.now(UTC)
    src_id = f"src-{sha256[:6]}"
    if (
        parsed.origin is not None
        and identity is not None
        and not parsed.origin.startswith(f"{identity.instance_id}:")
    ):
        return Source(
            id=src_id,
            url=f"external:{parsed.origin}",
            license="unknown",
            fetched_at=now,
            sha256=sha256,
            contribution=f"imported from {origin_tag or 'unknown'}",
        )
    author = identity.instance_id if identity else "unknown"
    return Source(
        id=src_id,
        url=f"local-author:{author}",
        license="unknown",
        fetched_at=now,
        sha256=sha256,
        contribution=f"imported from {origin_tag or 'manual'}",
    )
