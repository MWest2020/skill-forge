"""Sync promoted skills into consumer tools.

Spec: openspec/changes/add-plugin-bridges/proposal.md
"""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from skill_forge.storage.filesystem import live_skills_with_tag

# Built-in target → default consumer dir relative to ~ (use Path.home() at call time).
KNOWN_TARGETS: dict[str, str] = {
    "claude-code": ".claude/skills",
    "opencode": ".config/opencode/skills",
    "codex": ".agents/skills",  # per-repo, user typically overrides with --target-dir
}


class SyncError(Exception):
    """Wraps sync-specific failures (target-dir refused, manifest issues)."""


class SyncedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    target_path: str
    mode: str  # "symlink" | "copy"


class SyncManifest(BaseModel):
    """`sync/{target}.yml` — records what we've placed where."""

    model_config = ConfigDict(extra="forbid")
    target: str
    target_dir: str
    synced_at: datetime
    entries: list[SyncedEntry]


def sync_target(
    root: Path,
    *,
    target: str,
    target_dir: Path | None = None,
    mode: str = "symlink",
    tag: str | None = None,
) -> tuple[SyncManifest, int]:
    """Sync promoted skills into `target_dir`.

    Returns `(manifest, placed)` where `placed` is how many skills were synced
    *this run* — which differs from `len(manifest.entries)` under `--tag`, since
    a tagged sync merges into the manifest and preserves other skillsets' entries.

    Without `tag`, syncs every promoted skill (replacing the manifest). With
    `tag`, syncs only that skillset (live skills carrying the tag) and *merges*
    into any existing manifest — entries for other tags' skills are preserved —
    so a target can hold several skillsets. An empty skillset is an error.
    """
    if target not in KNOWN_TARGETS:
        raise SyncError(
            f"unknown target {target!r}; pick one of {sorted(KNOWN_TARGETS)} "
            "or pass --target-dir for a custom location"
        )
    resolved = _resolve_target_dir(target, target_dir)
    _refuse_dangerous_dir(resolved)
    if mode not in ("symlink", "copy"):
        raise SyncError(f"unknown mode {mode!r}; pick 'symlink' or 'copy'")
    # Symlinks on Windows are unreliable without admin; fall back to copy.
    if mode == "symlink" and os.name == "nt":
        mode = "copy"

    if tag is None:
        slugs = _list_promoted_slugs(root)
    else:
        slugs = live_skills_with_tag(root, tag)
        if not slugs:
            raise SyncError(f"no live skills tagged {tag!r}")

    placed = len(slugs)
    resolved.mkdir(parents=True, exist_ok=True)
    entries: list[SyncedEntry] = []
    for slug in slugs:
        src = root / "skills" / slug / "SKILL.md"
        dst_dir = resolved / slug
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "SKILL.md"
        _place(src, dst, mode=mode)
        entries.append(SyncedEntry(slug=slug, target_path=str(dst), mode=mode))

    if tag is not None:
        # Merge: keep entries for skills outside this skillset, replace the rest.
        existing = _read_manifest(root, target)
        if existing is not None:
            synced = {e.slug for e in entries}
            entries = [e for e in existing.entries if e.slug not in synced] + entries

    manifest = SyncManifest(
        target=target,
        target_dir=str(resolved),
        synced_at=datetime.now(UTC),
        entries=entries,
    )
    _write_manifest(root, target, manifest)
    return manifest, placed


def unsync_target(root: Path, *, target: str, tag: str | None = None) -> tuple[int, int]:
    """Remove synced entries from the previous manifest.

    Without `tag`, removes everything and deletes the manifest. With `tag`,
    removes only that skillset's entries (live skills carrying the tag) and
    rewrites the manifest with the rest — other skillsets stay mounted.

    Returns (removed, expected) — the latter lets callers tell users how
    many files were already gone vs how many we actually unlinked.
    """
    manifest = _read_manifest(root, target)
    if manifest is None:
        return 0, 0

    if tag is None:
        to_remove = manifest.entries
        remaining: list[SyncedEntry] = []
    else:
        tagged = set(live_skills_with_tag(root, tag))
        to_remove = [e for e in manifest.entries if e.slug in tagged]
        remaining = [e for e in manifest.entries if e.slug not in tagged]

    expected = len(to_remove)
    removed = 0
    for entry in to_remove:
        path = Path(entry.target_path)
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
                removed += 1
            parent = path.parent
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            continue

    manifest_path = root / "sync" / f"{target}.yml"
    if remaining:
        _write_manifest(root, target, manifest.model_copy(update={"entries": remaining}))
    elif manifest_path.exists():
        manifest_path.unlink()
    return removed, expected


def _resolve_target_dir(target: str, override: Path | None) -> Path:
    if override is not None:
        return override.expanduser()
    return Path.home() / KNOWN_TARGETS[target]


_REFUSED_SYSTEM_PATHS = {
    "/",
    "/etc",
    "/usr",
    "/var",
    "/bin",
    "/sbin",
    "/boot",
    "/root",
    "/dev",
    "/proc",
}


def _refuse_dangerous_dir(path: Path) -> None:
    """Refuse paths likely to be footguns: home, system roots, parents of $HOME."""
    resolved = path.resolve()
    home = Path.home().resolve()
    if resolved == home:
        raise SyncError(f"refusing to sync into your home directory ({resolved})")
    if str(resolved) in _REFUSED_SYSTEM_PATHS:
        raise SyncError(f"refusing to sync into a system directory ({resolved})")
    # Refuse ancestors of $HOME (e.g. /home, /Users on macOS).
    if resolved in home.parents:
        raise SyncError(f"refusing to sync into a parent of your home directory ({resolved})")
    if resolved.exists() and not resolved.is_dir():
        raise SyncError(f"{resolved} exists and is not a directory")


def _list_promoted_slugs(root: Path) -> list[str]:
    live = root / "skills"
    if not live.is_dir():
        return []
    return sorted(
        child.name
        for child in live.iterdir()
        if child.is_dir() and not child.name.startswith("_") and (child / "SKILL.md").is_file()
    )


def _place(src: Path, dst: Path, *, mode: str) -> None:
    # Handle the weird case where someone mkdir'd `SKILL.md/` at the target.
    if dst.is_dir() and not dst.is_symlink():
        shutil.rmtree(dst)
    elif dst.exists() or dst.is_symlink():
        dst.unlink()
    if mode == "symlink":
        dst.symlink_to(src)
    else:
        shutil.copy2(src, dst)


def _manifest_path(root: Path, target: str) -> Path:
    return root / "sync" / f"{target}.yml"


def _write_manifest(root: Path, target: str, manifest: SyncManifest) -> None:
    path = _manifest_path(root, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = manifest.model_dump(mode="json")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _read_manifest(root: Path, target: str) -> SyncManifest | None:
    path = _manifest_path(root, target)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SyncManifest(**data)
