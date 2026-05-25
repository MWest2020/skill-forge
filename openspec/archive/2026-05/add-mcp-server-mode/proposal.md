# add-mcp-server-mode

## Why

Filesystem sync (change #6) covers tools that read skills from disk on
session start. MCP-aware clients (Claude Desktop, Claude Code with MCP
config, any agent) prefer protocol access: list resources, read on
demand, no caching. Exposing skill-forge as an MCP server is the next
natural distribution surface, and it's the on-ramp to federation
(change #8 — peers speak MCP-over-HTTP to each other).

## What

- `forge serve mcp [--transport stdio|http] [--host 127.0.0.1] [--port 8765] [--token TOKEN]`
- MCP `resources/list` — one resource per promoted skill: URI
  `skill-forge://skill/{slug}`, name + description from frontmatter
- MCP `resources/read` — returns the full SKILL.md body for the slug
- stdio transport: standard MCP framing on stdin/stdout
- HTTP transport: bearer token required (from `--token`,
  `SKILL_FORGE_MCP_TOKEN` env, or refuse to start)
- v1 is read-only — no tools (`refine_skill` etc. come later)
- Implementation uses plain `httpx`/stdlib JSON-RPC, not the full
  `mcp` SDK package (keeps deps boring; the surface is small)

## Scope

- `src/skill_forge/mcp/{__init__,server,handlers}.py`
- `forge serve mcp` CLI command
- Tests: handler-level (resources/list + resources/read shape),
  stdio framing round-trip, HTTP auth gate
- README quickstart note

## Out of scope

- `tools/call` and the future `refine_skill` tool — read-only v1.
- TLS termination — recommend mTLS / Tailscale at the deployment
  layer, don't enforce it in code.
- Official-MCP-Registry publishing (`add-mcp-registry-publishing`
  sub-change after this).
- Caching strategy — `resources/list` reads from disk every time.
  Fast enough for personal-scale libraries (< 1000 skills).

## Risks

- **HTTP without TLS in deployments people will copy.** Mitigation:
  README explicitly recommends mTLS / Tailscale; CLI refuses to bind
  to non-loopback without `--token`.
- **MCP protocol drift.** Mitigation: implement the read-only subset
  precisely once and pin the protocol version we speak. If clients
  break, fail loudly with the version mismatch.
- **Token in argv visible via `ps`.** Mitigation: prefer
  `SKILL_FORGE_MCP_TOKEN` env var; document the trade-off.
