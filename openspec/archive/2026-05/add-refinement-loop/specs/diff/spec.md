# Spec — `forge diff`

Shows a unified diff between two iterations of a skill. Primary
review affordance before accept/reject.

## CLI

```
forge diff <slug> [--from vN] [--to vM] [--root PATH]
```

- `--from` and `--to` accept either `v<N>` or a bare integer.
- Defaults: `from = current_version - 1`, `to = current_version`.
  If `current_version` is 1, raises "no prior iteration to diff
  against" (exit 1).

## Backend resolution

1. Check `git --version`. If `git` is on PATH, use
   `git diff --no-index --color=always <from-file> <to-file>`. Stream
   stdout to the terminal directly (preserves color when isatty).
2. Otherwise, fall back to Python's `difflib.unified_diff` with
   ANSI-stripped output.

Both backends produce the same logical content (a unified diff). Git
is preferred because it handles trailing newlines and binary detection
better, and most developers expect git's output format.

## Source files

Read from `iterations/v{from}-*.md` and `iterations/v{to}-*.md`.
Missing iteration → raise `FileNotFoundError` with the version named.

## Exit codes

- `0` — diff produced (no exit-code distinction between "files
  differ" and "files identical"; git's `--exit-code` flag is
  deliberately not used).
- `1` — IO failure or unresolvable versions.

## Out of scope

- Side-by-side / word-level diffing.
- Diffing across slugs (cross-skill compare).
- Streaming diff for very large iterations (single read into memory
  is fine for markdown).
