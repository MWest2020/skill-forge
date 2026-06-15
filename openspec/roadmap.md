# Roadmap — superseded by what shipped (status, June 2026)

This file was a holding stub for changes #6 (plugin bridges) and #7 (MCP server
mode) from `STRATEGY.md`. Those shipped, then the distribution layer was
deliberately cut, and MCP came back in a much narrower form. The openspec
changes under `archive/` are now the source of truth; this file is just the map
from the old plan to today's reality.

## Status

| Sketched here | Reality | Where it lives |
|---|---|---|
| #6 `add-plugin-bridges` — `forge sync`, per-target manifest, symlink/copy | **Shipped**, plus `sync --tag` for skillset-scoped mounts. | `archive/2026-05/add-plugin-bridges`, `archive/2026-06/add-skillsets-and-mcp` |
| #7 `add-mcp-server-mode` — stdio **+ HTTP**, bearer token, `resources/*`, registry publishing | **Built (2026-05), then stripped, then rebuilt narrow.** Today: read-only `forge serve mcp` over **stdio only**, three tools (`list_skills`, `get_skill`, `get_skillset`). No HTTP, no token, no registry publishing. | `archive/2026-06/add-skillsets-and-mcp` |
| sync filters / frontmatter `tags` ("decide later") | **Shipped:** `tags` field + skillsets (a tag *query*, not a stored bundle); `ls --tag`, `forge tags`, `sync --tag`. | `archive/2026-06/add-skillsets-and-mcp` |
| #8 `add-federation` — peer-to-peer signed manifests, MCP-over-HTTP, trust modes | **Descoped.** Built in 2026-05, removed in `strip-to-curation-core`: skill-forge is one person's curated library, not a federation. | `changes/strip-to-curation-core` |

## What was deliberately dropped

`strip-to-curation-core` removed the entire **distribution** layer — federation
(`forge peer`), subscriptions (`forge subscribe` / `check-updates`), the old
broad MCP server (HTTP + token + registry publishing), and signed release
bundles. Reason: a single-user curated library never exercised it, and it was
the layer most exposed to being superseded by first-party skill tooling.

Do not reintroduce any of it without a fresh proposal. The one piece that came
back — a **read-only, stdio, tag-scoped** MCP server — exists only to let
containerized agents pull a specific skillset, not to distribute between
instances. See the June 2026 update in `STRATEGY.md` for the strategic framing.
