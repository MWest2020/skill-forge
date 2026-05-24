# Tasks — add-core-models-and-storage

One task = one commit. Check off as you go.

## Models

- [x] Write failing test `tests/test_models.py::test_skill_model_requires_name`
- [x] Implement `Skill` pydantic model (name, description, version, body, sources, judge_score, created)
- [x] Implement `Source` model (id, url, license, fetched_at, sha256, contribution)
- [x] Implement `JudgeScore` model (per-axis float scores + total, with weight-sum sanity check via Pydantic context)
- [x] Implement `Run` model (run_id, started_at, finished_at, topic, skill_slug, scores, promoted) — plus `RunSummary` for sources.yml
- [x] Round-trip tests: model -> dict -> model is identity

## Storage — filesystem adapter

- [x] `list_skills(root) -> list[SkillEntry]` returns live + draft entries (live alpha, then draft alpha)
- [x] `read_skill(root, slug) -> Skill` parses frontmatter + body, raises if missing
- [x] `read_sources(root, slug) -> SourcesFile` parses YAML, returns model
- [x] `write_skill(root, skill, draft=False)` writes SKILL.md to correct dir
- [x] `write_sources(root, slug, sources_file)` writes sources YAML
- [x] Collision behavior: writing an existing slug raises unless `overwrite=True`
- [x] `runs_path(root, run_id)` helper for change #3

  Skipped: committed fixture skills under `tests/fixtures/`. Tests build
  fixtures inline via `tmp_path` instead — same coverage, less file overhead.

## CLI

- [x] Wire `skill-forge ls` to `storage.list_skills` — rich table with slug, status, judge_score
- [x] Wire `skill-forge show <slug>` — two sections: SKILL.md (with on-disk path + live/draft), then sources.yml (or `[no provenance file]`)
- [x] CLI tests via `typer.testing.CliRunner`

## Validate

- [x] `ruff check` clean
- [x] `mypy --strict` clean on `src/`
- [x] `pytest` green (41 tests)
- [x] Live smoke: dropped a fixture under `skills/_draft/`, `uv run skill-forge ls` shows it with status + score, `uv run skill-forge show <slug>` prints SKILL.md + sources.yml; missing slug exits with code 1
