# Tasks — strip to curation core

## 1. Remove distribution modules

- [x] 1.1 Delete `src/skill_forge/federation/`
- [x] 1.2 Delete `src/skill_forge/subscribe/`
- [x] 1.3 Delete `src/skill_forge/mcp/`
- [x] 1.4 Delete `src/skill_forge/release.py`
- [x] 1.5 Delete `tests/test_federation.py`, `tests/test_subscribe.py`, `tests/test_mcp.py`, `tests/test_release.py`

## 2. Trim the CLI

- [x] 2.1 Remove `serve_app`, `peer_app`, `release_app` sub-apps + their `add_typer` calls
- [x] 2.2 Remove the `release`, `subscribe`, `check-updates`, `peer`, and `serve` command bodies
- [x] 2.3 Confirm no module-level imports of removed modules remain (only the kept `identity` import stays)

## 3. Verify the core is intact

- [x] 3.1 `uv run ruff check .` — clean
- [x] 3.2 `uv run pytest` — green (263 passed)
- [x] 3.3 Live smoke: `forge --help` lists the kept loop (import/judge/promote/refine/lineage/sync); `serve`/`peer`/`release`/`subscribe`/`check-updates` are gone

## 4. Docs & hygiene

- [x] 4.1 README: tagline, quickstart, layout, status table, known-gaps
- [x] 4.2 `.gitignore`: add `skills/_draft/`, `sources/`, `sync/`
- [x] 4.3 Delete moot untracked artifacts: `peers.yml`, `subscriptions.yml`, `releases/`, `website/`
