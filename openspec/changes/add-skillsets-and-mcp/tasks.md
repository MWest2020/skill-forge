# Tasks — add-skillsets-and-mcp

One commit per task, each referencing this change ID. TDD bias: the test lands
red first, the implementation turns it green. Tasks 1–4 (skillsets) are
independently shippable; 5–8 (MCP) build on them.

## Skillsets (`tags`)

- [x] **1. `tags` on the model.** Add `tags: list[str] = []` to `Skill` with
  the slug validator + dedup/sort. Tests: default `[]`; deduped+sorted; invalid
  tag rejected. **Note:** `tags` is excluded from `canonical_payload` —
  discovered that signing it would break the 7 existing signatures and is
  conceptually wrong (tags are mutable curation metadata, not authored
  provenance). Spec updated accordingly. `_KNOWN_SKILL_FIELDS` updated too.
  Renders as `tags: []` when empty (consistent with the all-fields convention),
  so the "no empty line" goal was dropped — noted in the spec.
- [x] **2. Storage query.** Added `storage.live_skills_with_tag(root, tag)`
  (live-only, sorted, empty on miss) and a `tags` field on `SkillEntry` so the
  ls Tags column (task 3) reuses the same scan. Tests cover the query + entry
  tags.
- [x] **3. `ls --tag` + `tags` command.** Added the `--tag` filter and a `Tags`
  column to `ls`; added `forge tags` (live tag counts, `No tags on live skills.`
  when empty). Tests via `CliRunner`.
- [x] **4. `sync --tag`.** `sync --tag T` mounts only the T skillset and merges
  into the manifest (other tags preserved); `--unsync --tag T` removes only T's
  entries and rewrites the manifest; empty skillset → exit 1. Tests cover mount,
  merge-preserving unsync, and the empty-skillset exit.

## MCP server

- [ ] **5. `serve` sub-app + stdio skeleton.** Add a `serve_app` Typer group and
  `forge serve mcp` that starts a stdio MCP server bound to `--root`. Test:
  server initializes and advertises the three tool schemas.
- [ ] **6. `list_skills` + `get_skill`.** Implement both read-only tools
  (live-only; `get_skill` errors cleanly on unknown/draft slug). Tests assert
  payload shape + draft invisibility.
- [ ] **7. `get_skillset`.** Implement the bundle tool over
  `live_skills_with_tag`; empty tag → `{tag, skills: []}`. Test the bundle and
  the empty case.
- [ ] **8. Read-only + provenance guarantees.** Assert no tool can reach draft
  skills, mutate state, or run a provider; every body payload carries `origin`.
  Add a README/`forge serve mcp --help` note on running it from a container.

## Validate (gate before archive)

- [ ] All tasks checked; specs match code; `ruff`, `mypy --strict`, `pytest`
  green.
- [ ] Live smoke: `forge serve mcp` answers a real `get_skillset("security")`
  returning the `owasp-security` body over stdio (no mocks).
