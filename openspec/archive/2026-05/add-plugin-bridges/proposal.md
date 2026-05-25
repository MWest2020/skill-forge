# add-plugin-bridges

## Why

The skill library is useless if it sits in `skill-forge` and doesn't reach
the tools Mark actually uses. `forge sync <target>` ships promoted skills
into the directory Claude Code (or OpenCode, or Codex) reads on session
start. Bidirectional: the `forge import-dir` path from change #2 already
covers consumer → forge.

## What

- `forge sync <target> [--mode symlink|copy] [--target-dir PATH] [--root PATH]`
  with built-in targets: `claude-code`, `opencode`, `codex`.
- Per-target conventional path (overridable via `--target-dir`):
  - `claude-code` → `~/.claude/skills/`
  - `opencode` → `~/.config/opencode/skills/`
  - `codex` → `.agents/skills/` (per-repo, run from inside the target repo)
- `--mode symlink` (default): each promoted skill's `SKILL.md` is symlinked
  into `{target_dir}/{slug}/SKILL.md`. Refinements propagate live.
- `--mode copy`: byte-copy. Snapshot semantics; user must re-sync after
  refinement.
- Per-target manifest at `sync/{target}.yml` records what got synced so
  `forge sync <target> --unsync` is precise.
- `forge sync <target> --unsync` removes everything in the manifest;
  silently skips anything the user has already removed/renamed.

## Scope

- `src/skill_forge/sync/{__init__,sync.py}` with `sync_one`, `sync_all`, `unsync`
- Sync manifest model + storage helpers
- `cli.py` — `sync` subcommand (single command, not a sub-typer, since the
  variants are flag-distinguished not subcommand-distinguished)
- Tests with tmp_path-based fake target dirs
- README quickstart updated to mention `forge sync claude-code`

## Out of scope

- Daemon / watch mode (`forge watch sync claude-code`). One-shot
  for MVP.
- Filters (`--tag kubernetes`, `--min-score 0.8`). Add when one target
  works end-to-end.
- Bidirectional sync (consumer edits → forge). Hard problem; out.
- Per-consumer special handling (e.g., Claude Code's plugin manifest
  vs. raw skills/). Just file placement for now.

## Risks

- **User points `--target-dir` at something dangerous.** Mitigation:
  refuse if the path exists and is not a directory or doesn't contain
  any existing `*.md` / is the home dir / is `/`. Conservative bail-out.
- **Pre-existing files in target dir.** Mitigation: refuse to overwrite
  files that aren't in our sync manifest. User runs `--unsync` then
  re-sync to recover.
- **Symlinks on Windows.** Mitigation: detect `os.name == "nt"` and
  fall back to copy mode with a one-line note. Not perfect, but
  Mark runs Linux.
