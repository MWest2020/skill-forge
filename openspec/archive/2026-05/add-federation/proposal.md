# add-federation

## Why

Six changes in, skill-forge has a curation loop, identity, lineage,
plugin bridges, and an MCP server. Federation is the last brick from
STRATEGY.md: peer instances exchange opt-in skills via signed
manifests, so an audited skill on instance A can land (with attribution
intact) on instance B. Mastodon-style: peer-to-peer, no central
registry, three trust modes.

## What

Reuses the MCP server from change #7 as the transport (peers POST
JSON-RPC over HTTP at `/mcp`). The federation surface is two new
read-only methods plus a CLI for managing peers and pulling skills.

- New MCP methods: `federation/peer-info` (returns this instance's
  public key + instance ID) and `federation/manifest` (returns a
  signed list of skills the peer is willing to share).
- Per-skill `visibility` field on the `Skill` frontmatter:
  `private` (default, never federated) | `unlisted` (returned in
  manifest only when requested by slug) | `public` (advertised in
  the manifest).
- `forge peer add <name> <url> [--token TOKEN]` — register a peer.
  Token used in the Authorization header for HTTP transport.
- `forge peer list` — show known peers + their cached instance IDs.
- `forge peer remove <name>` — drop a peer.
- `forge peer skills <name>` — fetch the peer's manifest, list
  candidate skills (slug + description + judge_score from the peer).
- `forge peer pull <name> <slug>` — fetch one skill by slug,
  verify peer signature, land it under `skills/_draft/{slug}/`
  with `origin` preserved (foreign), source provenance pointing at
  the peer URL, and a draft status.
- Trust modes (per-peer in `peers.yml`):
  - `reference-only` (default): peers visible in `forge peer skills`
    but `pull` requires explicit slug.
  - `review-queue`: same as reference-only for now; future change
    auto-pulls into a review-queue dir.
  - `auto-import` (dangerous): pull-everything. NOT implemented in
    MVP — config rejected with "not yet supported".

## Scope

- `src/skill_forge/federation/{__init__,peers,manifest,pull}.py`
- `src/skill_forge/mcp/handlers.py` — add `federation/*` methods
- `Skill` model: optional `visibility: Literal[...]` field with default
  `"private"`
- CLI `peer` sub-typer with `add`, `list`, `remove`, `skills`, `pull`
- `peers.yml` storage at repo root (alongside `sync/`)
- Tests with two local test servers exchanging skills

## Out of scope

- `auto-import` trust mode.
- Conflict resolution (peer A's skill collides with peer B's slug) —
  raise and skip for MVP.
- Push semantics (peers calling each other to notify of updates).
- Bandwidth limits / rate limiting.
- TLS at the federation layer — recommend Tailscale, document, don't
  enforce.

## Risks

- **Foreign-signature verification needs peer pubkey.** The pull flow
  hits `federation/peer-info` first to fetch and cache the peer's
  pubkey, then verifies the skill's signature with that key. If the
  cached pubkey is stale (peer regenerated identity), verification
  fails loudly.
- **Visibility leak via federation/manifest enumeration.** Mitigation:
  `private` skills are NEVER in the manifest (the filter happens at
  the response builder, not on the wire).
- **Peer impersonation.** Mitigation: instance_id is derived from the
  pubkey (`forge-{sha256(pubkey)[:8]}`); a peer can't fake an
  instance_id without owning the matching private key. We cache the
  first-seen pubkey per peer; mismatches on subsequent contact get
  a clear "peer's identity changed" error.
- **Pulled skill claims to be from a different peer.** Mitigation: on
  pull, we verify the skill's origin starts with the peer's
  instance_id. If a peer serves a skill claiming a different origin,
  reject with a clear error (don't silently store).
