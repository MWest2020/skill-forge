# Tasks — add-mcp-server-mode

- [x] mcp/handlers.py: dispatch + initialize + notifications/initialized + resources/list + resources/read
- [x] mcp/server.py: stdio (line-framed JSON-RPC) and HTTP (POST /mcp) transports
- [x] HTTP refuses non-loopback host without --token
- [x] forge serve mcp [--transport] [--host] [--port] [--token]
- [x] Tests: 16 (handlers + stdio + live HTTP server with token gating)
- [x] `/review` ran:
  - LOW: `log.exception` before -32603 re-raise (debugger keeps traceback, wire only carries message)
  - LOW: `hmac.compare_digest` for token comparison (defense in depth for tailnet exposure)
  - Notes: roll-our-own vs `mcp` SDK is defensible for read-only v1 surface; sync BaseHTTPRequestHandler fine for personal use
- [x] `/security-review` ran:
  - **HIGH**: path traversal in resources/read — slug not validated → could read `../etc/passwd` style. Drafts hidden by _list_resources also bypassable via `_draft/<slug>`. Fixed: validate slug against SLUG_RE before composing path. Regression test added.
  - LOW: timing-attack-able token compare — fixed via hmac.compare_digest
  - LOW: --token on argv leaks via ps on multi-user host — documented in --token help text, env var preferred
