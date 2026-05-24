# Change: add-core-models-and-storage

## Why

skill-forge is a pipeline that reads, scores, and writes structured artifacts
(skills + their provenance + per-run audit logs). Before any LLM call or
network code, we need a stable data layer: the types those artifacts are
represented as in memory, and the filesystem layout they live on disk.

Doing this first lets later changes (extraction, judge, discovery) plug into a
shared shape rather than each inventing its own.

## What

Introduces:

- Pydantic models `Skill`, `Source`, `Run`, `JudgeScore` with strict validation.
- A filesystem-backed storage adapter that reads and writes those models to the
  layout described in `openspec/project.md`.
- Working `skill-forge ls` and `skill-forge show <slug>` CLI commands backed by
  that adapter.

After this change, you can manually drop a `SKILL.md` + `sources.yml` into the
repo and inspect them through the CLI — no LLM involved.

## Scope

- `src/skill_forge/models.py`
- `src/skill_forge/storage/filesystem.py`
- `src/skill_forge/cli.py` — wire `ls` and `show` to storage
- `tests/test_models.py`, `tests/test_storage_filesystem.py`,
  `tests/test_cli_ls_show.py`
- A handful of fixture skills under `tests/fixtures/`

## Out of scope

- LLM providers, fetchers, judge, promoter — all later changes.
- `discover`, `extract`, `judge`, `run`, `promote`, `demote` CLI commands stay
  on `NotImplementedError`.
- No network code. No `httpx` use yet.
- No `runs/*.jsonl` writing (that lands with change #3).

## Risks

- Schema lock-in: if `Skill` or `sources.yml` shape needs to change later, every
  fixture and skill file needs migrating. Mitigation: keep the schema minimal,
  add a `version` field to both `Skill` frontmatter and `sources.yml` so future
  changes can be detected.
- Slug collisions: two skills with the same `name` would clobber each other.
  Storage layer must raise on collision rather than overwrite silently.
