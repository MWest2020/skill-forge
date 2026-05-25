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
) -> SyncManifest:
    """Sync every promoted skill into `target_dir`. Returns the new manifest."""
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

    promoted = _list_promoted_slugs(root)
    resolved.mkdir(parents=True, exist_ok=True)
    entries: list[SyncedEntry] = []
    for slug in promoted:
        src = root / "skills" / slug / "SKILL.md"
        dst_dir = resolved / slug
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "SKILL.md"
        _place(src, dst, mode=mode)
        entries.append(SyncedEntry(slug=slug, target_path=str(dst), mode=mode))

    manifest = SyncManifest(
        target=target,
        target_dir=str(resolved),
        synced_at=datetime.now(UTC),
        entries=entries,
    )
    _write_manifest(root, target, manifest)
    return manifest


def unsync_target(root: Path, *, target: str) -> int:
    """Remove every entry from the previous sync manifest. Returns count removed."""
    manifest = _read_manifest(root, target)
    if manifest is None:
        return 0
    removed = 0
    for entry in manifest.entries:
        path = Path(entry.target_path)
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
                removed += 1
            # Remove the {slug}/ parent if it's empty after our SKILL.md is gone.
            parent = path.parent
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            continue
    # Drop the manifest file itself so future sync starts clean.
    manifest_path = root / "sync" / f"{target}.yml"
    if manifest_path.exists():
        manifest_path.unlink()
    return removed


def _resolve_target_dir(target: str, override: Path | None) -> Path:
    if override is not None:
        return override.expanduser()
    return Path.home() / KNOWN_TARGETS[target]


def _refuse_dangerous_dir(path: Path) -> None:
    """Refuse paths that look like a user's home, /, or some other footgun."""
    resolved = path.resolve()
    if resolved == Path.home().resolve():
        raise SyncError(f"refusing to sync into your home directory ({resolved})")
    if str(resolved) in ("/", os.sep):
        raise SyncError(f"refusing to sync into root ({resolved})")
    if resolved.exists() and not resolved.is_dir():
        raise SyncError(f"{resolved} exists and is not a directory")


def _list_promoted_slugs(root: Path) -> list[str]:
    live = root / "skills"
    if not live.is_dir():
        return []
    return sorted(
        child.name
        for child in live.iterdir()
        if child.is_dir()
        and not child.name.startswith("_")
        and (child / "SKILL.md").is_file()
    )


def _place(src: Path, dst: Path, *, mode: str) -> None:
    if dst.exists() or dst.is_symlink():
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
