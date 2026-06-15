# Add skillsets + a read-only MCP server

## Why

`sync` mounts the curated library into a consumer's `~/.claude/skills` via
filesystem symlinks — same-host only. A new use case has appeared:
**containerized agents that need a specific subset of skills over a protocol**,
not a shared disk. A security-review container wants the `security` skillset; an
exam-prep container wants `examenstof`; neither should get the whole library or
reach the host filesystem.

Two things are missing for that:

1. **No grouping primitive.** Today a skill has `origin` (provenance) and a
   live/draft status — nothing that says "this skill belongs to the `security`
   set." `sync` is all-or-nothing.
2. **No transport.** `sync` is symlinks; a container can't consume that.

`mcp/` (`forge serve mcp`) was deliberately removed in
`strip-to-curation-core` because the old MCP surface served a *federation*
endgame the single-user library never exercised. This change does **not**
revive that. It adds the smallest grouping primitive (`tags`) and a narrow,
**read-only** MCP server whose only job is to hand a containerized agent the
skillset it asks for. Federation, subscribe, and release stay gone.

## What

**`tags` on skills (the skillset primitive).** A skill gains an optional
`tags: list[str]` frontmatter field. A *skillset* is defined as "every live
skill whose `tags` contain T" — a query, not a stored bundle. `tags` is
distinct from `origin` (which records *where a skill came from*); `tags` record
*what it is for*.

- `forge ls --tag T` and `forge sync <target> --tag T` filter by skillset.
- `forge tags` lists known tags with skill counts.

**`forge serve mcp` (read-only transport).** An MCP server over stdio that
exposes the *live* library only:

- `list_skills(tag?)` — slugs + descriptions, optionally filtered by tag.
- `get_skill(slug)` — one SKILL.md body + its provenance.
- `get_skillset(tag)` — every live SKILL.md carrying that tag, as a bundle.

No tool mutates state. Import/judge/promote/refine are not reachable over MCP.

## Scope

- `models.py`: add `tags` to the `Skill` model + frontmatter round-trip.
- `storage/filesystem.py`: persist/read `tags`; a `live_skills_with_tag` query.
- `cli.py` / `commands/`: `--tag` on `ls` and `sync`; a `tags` command; a new
  `serve` sub-app with `serve mcp`.
- `mcp/`: the read-only server (reintroduced, narrowly).
- `tests/`: contracts for tag round-trip, tag filtering, and each MCP tool.

## Out of scope

The reasons `strip-to-curation-core` cut these still hold — do **not**
reintroduce:

- **Federation** (`forge peer`, manifest exchange between instances).
- **Subscribe / check-updates** (pulling from peers).
- **Release bundles** (signed, version-pinned snapshots).
- **Write access over MCP** — no remote import/promote/judge/refine.
- A stored "skillset" object / registry — a skillset is a tag query, nothing
  more. If named bundles are ever needed, that is a separate proposal.

## Risks

- **Scope creep back to federation.** A read-only skillset server is one step
  from "let peers pull" — the exact surface just removed. Mitigation: the
  server is read-only and tag-scoped by contract; "Out of scope" is explicit;
  no peer/identity-exchange tools exist.
- **Tag sprawl.** Free-text tags rot into near-duplicates (`sec`, `security`).
  Mitigation: `forge tags` surfaces the live set so drift is visible; tags are
  validated as slugs. First noticed via `forge tags` showing siblings.
- **MCP transport drift.** The MCP SDK surface changes. Mitigation: one thin
  server module, contracts pinned by tests against the tool schemas; stdio
  only (no HTTP/auth surface) until a container actually needs more.
- **Skillset can be split off.** The `tags` capability ships and is useful
  alone (filtered `sync`); MCP builds on it. If review gets heavy, land
  `skillsets` first and `mcp-server` as a follow-up change.
