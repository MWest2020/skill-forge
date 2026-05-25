"""Sync promoted skills into consumer tools (Claude Code, OpenCode, Codex)."""

from .sync import (
    KNOWN_TARGETS,
    SyncError,
    SyncManifest,
    sync_target,
    unsync_target,
)

__all__ = [
    "KNOWN_TARGETS",
    "SyncError",
    "SyncManifest",
    "sync_target",
    "unsync_target",
]
