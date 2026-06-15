# Spec — `forge serve mcp`

## Signature

```
forge serve mcp [--root PATH]
```

- `--root PATH`: project root containing the `skills/` tree. Defaults to cwd.
- Speaks the Model Context Protocol over **stdio** (one process per consumer,
  e.g. a container running `forge serve mcp`). No HTTP, no auth, no network
  listener.

## Exposed tools

All tools are **read-only** and operate on the **live** library only (draft
skills are invisible over MCP). All return structured JSON.

### `list_skills(tag?: str) -> [{slug, description, tags}]`

Live skills, optionally filtered to those carrying `tag`. Sorted by slug. No
SKILL.md bodies (cheap listing). Unknown/absent tag with no matches → `[]`.

### `get_skill(slug: str) -> {slug, body, tags, origin, version}`

One live skill: its full SKILL.md `body`, `tags`, provenance `origin`, and
`version`. Unknown or draft-only slug → MCP tool error `skill not found:
<slug>` (does not crash the server).

### `get_skillset(tag: str) -> {tag, skills: [{slug, body, tags, origin, version}]}`

Every live skill carrying `tag`, bodies included — the bundle a container
mounts. Empty skillset → `{tag, skills: []}` (not an error; the consumer
decides whether empty is fatal).

## Guarantees

- **Read-only.** No tool imports, judges, promotes, demotes, or refines. The
  server opens nothing under `skills/_draft/`, writes nothing, and runs no LLM
  provider.
- **Provenance preserved.** Every body-returning tool includes `origin` so a
  consuming agent can record where a mounted skill came from.
- **Live-only.** A skill must be promoted to be visible; this matches what
  `sync` mounts, so MCP and `sync` expose the same set for a given tag.

## Non-goals

- No write tools (intake/curation stays local-only — see proposal Out of
  scope).
- No peer/federation/subscription tools.
- No HTTP transport or authentication until a deployed container needs it; that
  is a separate proposal.
- No streaming/watch — a consumer re-calls `get_skillset` to refresh.
