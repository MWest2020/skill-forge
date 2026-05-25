# Tasks — add-plugin-bridges

- [x] sync/sync.py with sync_target + unsync_target + SyncManifest model
- [x] KNOWN_TARGETS: claude-code, opencode, codex
- [x] symlink mode (default) with Windows fallback to copy
- [x] copy mode
- [x] per-target manifest at sync/{target}.yml (atomic write)
- [x] forge sync <target> CLI command with --target-dir, --mode, --unsync
- [x] Tests: 13 sync + 2 added on review feedback (system dirs, home parent)
- [x] `/review` ran, fixes applied:
  - LOW: `_refuse_dangerous_dir` expanded with `/etc`, `/usr`, `/var`, `/bin`, `/sbin`, `/boot`, `/root`, `/dev`, `/proc` and refuses parents of $HOME (catches `--target-dir /home` typo)
  - LOW: `unsync_target` now returns `(removed, expected)` tuple; CLI prints `Unsynced: X of Y skill(s) removed`
  - LOW: `_place` now handles dst-is-directory case (a manually-mkdir'd `SKILL.md/`) via `shutil.rmtree`
- [x] `/security-review` — clean, no findings (single-user threat model)
