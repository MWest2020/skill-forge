# Spec — storage (filesystem adapter)

Pure I/O over the layout described in `openspec/project.md`. No business logic.

## Layout

```
{root}/
├── skills/
│   ├── {slug}/SKILL.md         # live, promoted
│   └── _draft/
│       └── {slug}/SKILL.md     # draft (below threshold or pending review)
├── sources/
│   └── {slug}.yml              # provenance for one skill
└── runs/
    └── {run_id}.jsonl          # one JSON object per pipeline step, append-only
```

`runs/` is **not** written by this change — it appears in change #3. The
storage adapter still exposes a `runs_path(root, run_id)` helper so later code
has one place to ask.

## API

```python
def list_skills(root: Path) -> list[SkillEntry]: ...
def read_skill(root: Path, slug: str) -> Skill: ...
def read_sources(root: Path, slug: str) -> SourcesFile: ...
def write_skill(root: Path, skill: Skill, *, draft: bool, overwrite: bool = False) -> Path: ...
def write_sources(root: Path, slug: str, sources_file: SourcesFile, *, overwrite: bool = False) -> Path: ...
```

`SkillEntry` is a small dataclass: `{slug, draft, judge_score | None}`.

## Behavior

- `list_skills` scans both `skills/<slug>/SKILL.md` and `skills/_draft/<slug>/SKILL.md`.
  Order: live first (alpha), then drafts (alpha). Skips files that don't parse.
- `read_skill` prefers `skills/<slug>` over `skills/_draft/<slug>`. If neither
  exists, raises `FileNotFoundError` with a clear message naming both paths
  checked.
- Frontmatter parsing uses `pyyaml.safe_load`; body is everything after the
  closing `---`. Frontmatter delimiter must be the first non-empty line —
  reject otherwise.
- `read_sources` parses YAML and validates against the `SourcesFile` model
  (defined under models spec extension: a `sources` list + optional `runs` list).
- `write_skill` creates the slug folder if missing. Writes `SKILL.md`. Refuses
  to clobber an existing file unless `overwrite=True`.
- `write_sources` writes `sources/{slug}.yml`. Same overwrite rule.

## Failure modes

- Missing slug → `FileNotFoundError`.
- Malformed frontmatter → `ValueError` with the path and a one-line reason.
- Slug collision on write without `overwrite=True` → `FileExistsError`.
- Filesystem permission error → bubbled up as `PermissionError` (don't wrap).
