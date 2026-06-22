# Strip to curation core

## Why

skill-forge accreted machinery for **sharing skills between instances** —
peer-to-peer federation, subscriptions, an MCP server surface, and signed
versioned release bundles. That made sense under the original STRATEGY.md
endgame (a Mastodon-style federation of skill libraries). In practice the
tool is used by one person for one purpose: **a curated, self-improving
personal library**. The distribution machinery is maintenance surface that
the actual use case never exercises, and it is the layer most exposed to
being superseded by Anthropic's own skill tooling.

This change cuts skill-forge back to the curation core and keeps only what
serves "curated libs + self-improvement".

## What

**Removed:**
- `federation/` — `forge peer` (add/list/remove/skills/pull); peer-to-peer
  signed-manifest exchange.
- `subscribe/` — `forge subscribe` / `check-updates`; pulling updates from
  peer instances.
- `mcp/` — `forge serve mcp`; the read-only MCP server (stdio/HTTP)
  distribution surface.
- `release.py` — `forge release create/list/verify`; signed, version-pinned
  bundles.
- The corresponding CLI sub-apps (`serve_app`, `peer_app`, `release_app`),
  command bodies, and their test modules.
- `website/` (untracked static-site artifact).

**Kept (the curation + self-improvement loop):**
- Intake: `import`, `import-repo`, `import-dir`, `extract`, `discover`,
  `run`.
- `judge` (rubric scoring), `promote` / `demote`.
- `refine`, `refine-accept`, `refine-reject`, `lineage`, `diff` — the
  self-improvement loop.
- `sync` (mount into Claude Code / OpenCode / …) — how the library is used.
- Local provenance **identity** (`identity.py`): the Ed25519 author stamp
  (`origin` + `signature`) threaded through every import/judge/promote/refine.
  It is a per-skill provenance stamp, not a federation feature, so it stays.
- **Source citation** (the cite half of the old `add-subscribe-and-cite`):
  it lives in the core (`models`, `import_skill`, `storage`, provider
  prompts), not in `subscribe/`, and is a hard requirement — kept.

## Scope

- `src/skill_forge/`: delete `federation/`, `subscribe/`, `mcp/`,
  `release.py`; trim `cli.py` (sub-apps + command blocks).
- `tests/`: delete `test_federation.py`, `test_subscribe.py`,
  `test_mcp.py`, `test_release.py`.
- `README.md`: drop stripped commands from the tagline, quickstart, layout,
  status table, and known-gaps.
- Untracked cleanup: delete `peers.yml`, `subscriptions.yml`, `releases/`,
  `website/`; gitignore `skills/_draft/`, `sources/`, `sync/` as local
  working state.

## Out of scope

- No change to the curation loop's behaviour — same commands, same scores,
  same files.
- The `identity` keypair and per-skill signatures are untouched (provenance,
  not distribution).
- Source citation in skill bodies is untouched.
- STRATEGY.md's broader framing is not rewritten here; the README status
  section records the descope and points at this change.

## Risks

- **A kept module secretly imports a removed one.** Mitigated: a tree-wide
  grep confirmed `federation`/`subscribe`/`mcp`/`release` were imported only
  by `cli.py` and their own tests; the full suite (263 tests) and `ruff`
  pass after removal, and `forge --help` loads with the kept commands
  present and stripped commands absent.
- **`identity` looked like a federation feature.** It is not — every core
  command threads `identity=` for the provenance stamp. Removing it would
  break the core, so it stays. This is the one place the strip is narrower
  than "remove everything federation-adjacent".
- **Losing release/federation forecloses future distribution.** Accepted:
  the git history and archived change folders preserve the implementations;
  if a real multi-instance need appears, they can be revived from history.
