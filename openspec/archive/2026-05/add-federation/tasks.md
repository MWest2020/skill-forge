# Tasks — add-federation

- [x] Skill.visibility field (private | unlisted | public, default private)
- [x] federation/peers.py: Peer + PeersFile + add/remove/list/read/write
- [x] federation/pull.py: fetch_manifest / fetch_peer_info / pull_skill
  with origin-prefix + Ed25519 signature verification
- [x] mcp/handlers.py: federation/peer-info + federation/manifest + federation/skill
  methods, private skills hidden, unlisted callable-by-slug
- [x] forge peer add|list|remove|skills|pull CLI
- [x] Tests: 15 (peers CRUD, federation/* method shapes, end-to-end pull
  between two local HTTPServer instances, foreign-origin rejection)
- [x] `/review` ran:
  - LOW: resources/list (the change #7 method) was leaking unlisted/private
    slugs to anyone with the MCP token → filtered to public-only,
    matching federation/manifest semantics
  - LOW: TOFU note added to `forge peer add` output
  - LOW: _ensure_peer_identity now refuses to write back if the peer
    was removed mid-pull (silent-resurrection guard)
- [x] `/security-review` ran — clean, no qualifying findings
- [x] 281 tests total, ruff + mypy --strict clean
