# Tasks — add-core-models-and-storage

One task = one commit. Check off as you go.

## Models

- [ ] Write failing test `tests/test_models.py::test_skill_model_requires_name`
- [ ] Implement `Skill` pydantic model (name, description, version, body, sources, judge_score, created)
- [ ] Implement `Source` model (id, url, license, fetched_at, sha256, contribution)
- [ ] Implement `JudgeScore` model (per-axis float scores + total, with weight-sum sanity check)
- [ ] Implement `Run` model (run_id, started_at, finished_at, topic, skill_slug, scores, promoted)
- [ ] Round-trip tests: model -> dict -> model is identity

## Storage — filesystem adapter

- [ ] `list_skills(root) -> list[str]` returns live + draft slugs, draft slugs prefixed `_draft/`
- [ ] `read_skill(root, slug) -> Skill` parses frontmatter + body, raises if missing
- [ ] `read_sources(root, slug) -> SourcesFile` parses YAML, returns model
- [ ] `write_skill(root, skill, draft=False)` writes SKILL.md to correct dir
- [ ] `write_sources(root, slug, sources_file)` writes sources YAML
- [ ] Collision behavior: writing an existing slug raises unless `overwrite=True`
- [ ] Fixture skills under `tests/fixtures/skills/` and `tests/fixtures/sources/`

## CLI

- [ ] Wire `skill-forge ls` to `storage.list_skills` — table with slug, draft flag, judge_score
- [ ] Wire `skill-forge show <slug>` — print SKILL.md, then sources.yml
- [ ] CLI tests via `typer.testing.CliRunner`

## Validate

- [ ] `ruff check` clean
- [ ] `mypy --strict` clean on `src/`
- [ ] `pytest` green
- [ ] Live smoke: drop a real fixture, `uv run skill-forge ls` shows it, `uv run skill-forge show <slug>` prints it
