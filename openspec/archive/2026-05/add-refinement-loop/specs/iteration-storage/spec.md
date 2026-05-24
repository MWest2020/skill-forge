# Spec — iteration storage

## On-disk layout (per skill)

```
skills/{slug}/SKILL.md          # always equals iterations/v{current}-*.md
skills/{slug}/lineage.yml       # index — see lineage spec
skills/{slug}/iterations/
    v1-imported-2026-05-24.md   # the historical iterations, never deleted
    v2-refined-2026-05-26.md
    v3-refined-2026-05-27.md
```

Same shape under `skills/_draft/{slug}/`.

`SKILL.md` is duplicated for consumer ergonomics (and so `forge ls` /
`forge show` don't need to understand the layout). Always equals the
file in `iterations/` whose version matches `lineage.current_version`.

## Filename convention

```
v{version}-{kind}-{YYYY-MM-DD}.md
```

- `version` — monotonic int starting at 1.
- `kind` — one of `imported`, `extracted`, `refined`, `accepted`.
  `accepted` records that the user explicitly promoted this iteration
  to be `current`; the file content is identical to whatever
  `v{N-1}-{kind}-*.md` it accepted.
- date — ISO date, UTC.

The regex `r"^v(\d+)-(imported|extracted|refined|accepted)-(\d{4}-\d{2}-\d{2})\.md$"`
parses every iteration filename.

## API (in `src/skill_forge/storage/filesystem.py`)

```python
def iterations_dir(root: Path, slug: str, *, draft: bool) -> Path: ...

def write_iteration(
    root: Path,
    slug: str,
    *,
    body: str,
    version: int,
    kind: str,
    created: date,
    draft: bool,
) -> Path: ...

def read_iteration(root: Path, slug: str, version: int, *, draft: bool) -> str: ...

def list_iterations(root: Path, slug: str, *, draft: bool) -> list[Iteration]: ...
```

`Iteration` is the metadata-only record (version + kind + created +
optional judge_score), separate from the body text on disk. Reading
the body is cheap so we expose them apart.

## Backward compat

Existing skills (pre-change-#3) are flat — a single `SKILL.md` with
no `iterations/` or `lineage.yml`. They keep working: `forge ls`,
`forge show`, `forge judge`, `forge promote`, `forge demote` are all
oblivious to the new layout for legacy skills. Operations that
explicitly want iteration semantics (`forge refine`, `forge diff`,
`forge refine-accept`/`reject`) raise a clear "this skill hasn't been
migrated yet — run `forge lineage migrate <slug>`" error when invoked
on a flat skill.

## Migration

`forge lineage migrate [--root PATH] [--dry-run] [--slug SLUG]` walks
every flat skill under `skills/` and `skills/_draft/`, and for each:

1. Creates `iterations/v1-imported-{today}.md` as a byte-for-byte
   copy of the existing `SKILL.md`. (`kind=imported` because we don't
   know which intake path produced it.)
2. Writes `lineage.yml` with `current_version=1` and one entry in
   `iterations`.
3. Leaves `SKILL.md` in place — by spec, it equals the current
   iteration, so no rewrite needed.

Idempotent: if `lineage.yml` already exists, the skill is skipped.
`--dry-run` prints the plan; `--slug` limits to one skill.

## Out of scope

- Iteration pruning (`forge lineage prune`). Later.
- Branching iterations. The lineage is linear; if you want a fork,
  copy the skill to a new slug.
