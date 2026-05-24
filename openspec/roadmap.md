# Roadmap stub — plugin bridges & MCP server mode

This file is a holding place for changes #6 and #7 from `STRATEGY.md`. Not a change proposal yet — those land when changes #1 – #3 are validated and the curation loop is proven. Capturing the shape here keeps the architectural decisions of earlier changes compatible with this direction.

## Change #6: add-plugin-bridges

### Goal

Make skill-forge useful inside the tools people already use, without forcing them to abandon those tools. Two directions:

**skill-forge → consumer (export):**

| Target | Conventional path | Mechanism |
|---|---|---|
| Claude Code | `~/.claude/skills/` | Symlink each `skills/{slug}/SKILL.md` into target. Iterations stay in skill-forge. |
| OpenCode | `~/.config/opencode/skills/{slug}/SKILL.md` | Same pattern. |
| OpenAI Codex | `.agents/skills/{slug}/SKILL.md` per repo | Per-repo target, configured per-sync. |
| Antigravity / Cursor / Copilot | TBD per docs at the time | Same shape. |

CLI: `forge sync <target> [--mode symlink|copy] [--target-dir PATH]`.

A sync manifest at `sync/{target}.yml` records what is currently synced so `forge sync <target> --unsync` is precise.

**consumer → skill-forge (import-dir already covers this):**

`forge import-dir ~/.claude/skills --origin-tag external/claude-code` is the existing path. No new change needed for the consumer-to-forge direction; change #2 already covers it.

### Decisions to defer to change start

- Symlink vs copy as default. Depends on whether the target tool watches for inode changes. Claude Code reads on session start, so either works; symlinks propagate refinement live, copies do not.
- Whether sync is one-shot (`forge sync claude-code`) or daemon (`forge watch sync claude-code`). One-shot is simpler and the right MVP; watching is a follow-up.
- Whether to support sync **filters** (only skills with `tag: kubernetes`, only score ≥ X). Useful but adds CLI complexity. Decide after one sync target works.

### Out of scope for change #6

- Running skill-forge as a Claude Code or OpenCode plugin with its own command palette entries. Different integration surface, much larger change. Possibly worth doing for one consumer once the static sync works.
- Bidirectional sync (consumer edits propagating back to skill-forge). Hard problem with conflicting edits. Out.

## Change #7: add-mcp-server-mode

### Goal

Expose the skill library as an MCP server so any MCP-aware client can read skills on demand, no filesystem sync required.

### Surface

`forge serve mcp [--transport stdio|http] [--host 127.0.0.1] [--port 8765] [--token TOKEN]`.

MCP resources:

- `resources/list` — returns slug + description for every promoted skill.
- `resources/read/{slug}` — returns the full SKILL.md content as a resource.
- Optionally `resources/list?prefix=tag:` — filter by frontmatter tags (if we add tags by then).

MCP tools (v1: none. read-only is enough for the first release):

- A later sub-change adds `tools/call: refine_skill` so an external agent can request a refinement via MCP. Out of scope for v1.

### Auth

- stdio: trust the parent process.
- HTTP: bearer token required. Token configured via `--token` or `SKILL_FORGE_MCP_TOKEN` env var. Missing token over HTTP = 401.
- Recommended deployment (documented, not enforced): mTLS or Tailscale tailnet. The user owns the network layer; skill-forge owns the application layer.

### Registry publishing

Sub-change `add-mcp-registry-publishing`:

- `server.json` in the repo following the official registry schema.
- GitHub Action to publish on tagged releases.
- Namespace: `io.github.MWest2020/skill-forge` (if the GitHub user-owner stays the same) or `io.github.conduction/skill-forge` if it moves under Conduction's org.
- Submission to community registries (mcp.so, Smithery, Glama) deferred until the official one is live.

### Decisions to defer

- Whether the MCP server reads from `skills/` directly or through a small index built at start. Directly is simplest; an index is faster for large libraries (> 1000 skills). Decide based on real numbers.
- Whether to expose `runs/` and `lineage.yml` as MCP resources. Useful for an external agent that wants to refine; risky if the server is public. Default: do not expose. Behind a flag, expose to authenticated callers.

## Change #8: add-federation

The biggest deferred change. `STRATEGY.md` captures the high-level pattern (peer-to-peer signed manifests, MCP-over-HTTP as the candidate protocol, three trust modes with `review-queue` as default). When this change starts, the first task is a real protocol spec, not code.

Federation explicitly depends on:

- Change #1 (identity) — federation is impossible without signed origin.
- Change #3 (lineage) — federation ships lineage so peers can see the iteration history.
- Change #7 (MCP server mode) — the transport is MCP-over-HTTP between peer instances.

This dependency chain is why federation is change #8 and not change #4.

## Non-roadmap notes

- The names `skill-forge.dev`, `forge.skills`, `skillforge.io` are unchecked. Decide once the curation loop is in real-world use and a domain is actually needed.
- A "verified by skill-forge" badge for skills above threshold is **not** on the roadmap. Badges become governance theatre quickly. Lineage is the audit trail; trust is per-instance.
