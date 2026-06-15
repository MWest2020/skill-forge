# Tasks — add-skillsets-and-mcp

One commit per task, each referencing this change ID. TDD bias: the test lands
red first, the implementation turns it green. Tasks 1–4 (skillsets) are
independently shippable; 5–8 (MCP) build on them.

## Skillsets (`tags`)

- [ ] **1. `tags` on the model.** Add `tags: list[str] = []` to `Skill` with
  the slug validator + dedup/sort on write. Test: a skill round-trips tags;
  invalid tag rejected; missing key → `[]` and no empty `tags:` emitted.
- [ ] **2. Storage query.** Add `storage.live_skills_with_tag(root, tag)`
  (live-only, sorted, empty on miss). Test against a fixture tree with mixed
  live/draft + tags.
- [ ] **3. `ls --tag` + `tags` command.** Add the `--tag` filter and `Tags`
  column to `ls`; add `forge tags` (live tag counts). Tests via `CliRunner`.
- [ ] **4. `sync --tag`.** Filter `sync`/`--unsync` to a skillset; exit 1 on an
  empty skillset. Test: tagged subset mounts; other tags untouched on
  `--unsync --tag`; empty skillset exits 1.

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
