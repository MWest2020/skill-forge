# Spec — import

Lives at `src/skill_forge/import_skill/`. Module name avoids shadowing the
Python `import` builtin.

## API

```python
def import_file(
    root: Path,
    path: Path,
    *,
    identity: Identity | None = None,
    origin_tag: str | None = None,
    overwrite: bool = False,
) -> tuple[Skill, list[Source]]: ...

def import_directory(
    root: Path,
    src_dir: Path,
    *,
    identity: Identity | None = None,
    origin_tag: str | None = None,
) -> list[tuple[Skill, list[Source]]]: ...
```

Both return the parsed Skill + the Sources written to provenance, so callers
(CLI, tests) can audit what landed without re-reading from disk.

## Behavior

1. **Parse** the candidate SKILL.md via `storage._read_skill_file` (frontmatter
   + body). If parsing or model validation fails, raise `ImportError` with the
   path and the underlying message. **No bytes are written on failure.**
2. **Slug collision**: if the parsed `skill.name` already exists under
   `skills/{slug}` or `skills/_draft/{slug}`, auto-suffix `-2`, `-3`, ...
   (reuses `_free_slug` from cli.py — promoted to a shared helper in storage).
3. **Compute** `body_sha256` of the original file bytes (before any
   re-serialization) — captured into the Source record for auditability.
4. **Write** the skill to `skills/_draft/{slug}/SKILL.md` via
   `storage.write_skill(..., draft=True, identity=identity)`. The identity
   stamping rules from change #1 apply: stamps origin + signature when
   missing AND when origin is ours; preserves foreign origin verbatim.
5. **Write** the provenance to `sources/{slug}.yml` with:
   - If the parsed Skill carries an `origin` field that is **not** ours,
     one Source with `url=external:{origin}`, `license="unknown"`, the
     captured `sha256`, and contribution `imported from {origin_tag or 'unknown'}`.
   - Otherwise, one Source with `url=local-author:{identity.instance_id or 'unknown'}`,
     `license="unknown"`, the captured `sha256`, and contribution
     `imported from {origin_tag or 'manual'}`.
6. **Audit**: append a `Run` event with `event="imported"`,
   `skill_slug=<slug>`, `topic=None` to `runs/{run_id}.jsonl`.

`import_directory` walks `src_dir`'s immediate children, treating each
subdirectory that contains a `SKILL.md` as one importable skill. Files
without a SKILL.md sibling are skipped silently. Each successful import
contributes one entry to the returned list; failures are accumulated and
re-raised at the end as an `ImportErrorGroup` so partial progress is visible.

## CLI

```
forge import <path> [--origin-tag TAG] [--root PATH]
forge import-dir <dir> [--origin-tag TAG] [--root PATH]
```

- `--origin-tag` annotates Source.contribution to record provenance class
  (`external/claude-code`, `microsoft/skills`, `manual`, etc.). Stored as a
  free-form string until a future `Source.origin_tag` field exists.
- Exit codes: `0` ok, `1` parse/validation failure, `2` config/identity issue.

## Out of scope

- License detection (lands with change #4 `add-discovery`).
- Refinement / merging an imported skill with an existing one
  (change #3 `add-refinement-loop`).
- Watch mode (`forge import-dir --watch`).
