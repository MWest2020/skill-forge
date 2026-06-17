# skill-forge

> Local CLI to curate an owned library of Anthropic-style **SKILL.md** files —
> import from anywhere, score against a rubric, refine across iterations, and
> mount into the tools you use. License-aware and provenance-tracked end to end.

## What it is

A personal knowledge pipeline. Curiosities, DevOps patterns, work processes,
component docs — anything currently spread across docs, blog posts, and own
notes — gets one structured form that Claude Code and other agents can mount.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:MWest2020/skill-forge.git
cd skill-forge
uv sync
```

LLM stages default to the `claude_code` provider, which uses your Claude Code
subscription via the `claude` binary — no API key required. To use the
pay-per-token Anthropic API instead, set `providers.*: anthropic` in
`config/default.yml` and export `ANTHROPIC_API_KEY`. A local Ollama model is a
third option (`providers.*: ollama`).

## Quickstart

The full curation loop is live. Skills enter as drafts, get scored, and
graduate to live when they clear the threshold.

```bash
# Bring skills in. import-repo walks a GitHub repo and normalizes every
# SKILL.md it finds (injects version/created/sources, strips foreign fields).
uv run forge import-repo https://github.com/anthropics/skills --origin-tag external/anthropics-skills

# See what landed (everything imports as draft)
uv run forge ls
uv run forge show claude-api

# Score a draft against the rubric (LLM judge). Eight axes (rubric v2: schema,
# clarity, actionability, gap-coverage, provenance, structural-clarity,
# example-grounding, tool-declaration). Scored N times (default 3) and reduced
# by per-axis median to tame LLM non-determinism; full provenance (model, rubric
# version, prompt hash, every raw run) lands in the audit trail. Bumping the
# rubric version makes old scores stale (tagged with their version) — re-judge
# to refresh; nothing is auto-demoted.
uv run forge judge claude-api
uv run forge judge claude-api --explain   # show the recorded provenance for the latest score

# Read-only verdict — no promote, no audit, no writes. Accepts an imported slug
# OR a path to a raw SKILL.md, so it lints skills you haven't adopted yet
# (wire it into a CI quality gate; --runs 1 for speed).
uv run forge advise ./some/unimported/SKILL.md --runs 1

# Promote drafts that clear the threshold (total ≥ 0.75, every axis ≥ 0.50)
uv run forge promote claude-api

# Mount your live skills into a consumer tool (Claude Code, OpenCode, …)
uv run forge sync claude-code --mode symlink
```

Group skills into **skillsets** with `tags`, then mount or serve a subset:

```bash
uv run forge tags                                 # tags on live skills, with counts
uv run forge ls --tag security                    # just the security skillset
uv run forge sync claude-code --tag security      # mount only that skillset

# Serve the live library read-only over MCP (stdio) — for containerized agents
# that pull a specific skillset instead of sharing a disk:
uv run forge serve mcp                             # tools: list_skills, get_skill, get_skillset
```

A *skillset* is a query ("live skills tagged T"), not a stored bundle. The MCP
surface is read-only: it exposes the live library, never intake or curation.

The refinement loop — improve a skill across scored iterations:

```bash
uv run forge lineage migrate --slug claude-api   # one-time: flat → iteration-aware
uv run forge refine claude-api --prompt "tighten the when-to-use section"
uv run forge diff claude-api                      # review v(n-1) → v(n)
uv run forge refine-accept claude-api --iteration 2
```

Other intake paths:

```bash
uv run forge extract https://example.com/post    # distill one URL into a draft
uv run forge run "kubernetes pvc resize"          # discover + extract + judge, end to end
uv run forge import ./path/to/SKILL.md            # import one local SKILL.md
```

All import paths (`import`, `import-dir`, `import-repo`) normalize a vanilla
Anthropic skill — just `name` + `description` — by injecting the required
`version` / `created` / `sources` and stripping foreign frontmatter.

## License policy

`skill-forge` respects source licenses. Output is paraphrased via LLM (no
verbatim reproduction), attributed, and license-tagged in `sources/{slug}.yml`.
Sources whose ToS forbids automated access, or whose license is unclear or
restrictive, are skipped and logged to `discovery_blocked.log`.

| Class | Treatment |
|---|---|
| Permissive (MIT, Apache-2.0, CC-BY, public domain) | Extract + attribute |
| Copyleft (GPL, AGPL, CC-BY-SA) | Extract + attribute + share-alike note |
| Restrictive (CC-BY-NC, proprietary with explicit permission) | Extract for personal use only |
| Forbidden (ToS-blocked, paywalled, unclear) | Skip + log |

Output is intended for personal and/or internal use. Redistribution depends on
the source license.

## Layout

```
skill-forge/
├── src/skill_forge/        # the tool itself
├── skills/                 # promoted skills (live), with per-skill iterations/
│   └── _draft/             # pending/rejected drafts (local working area, gitignored)
├── sources/                # provenance per draft skill (gitignored working area)
├── sync/                   # per-target sync manifests (sync claude-code, gitignored)
├── runs/                   # JSONL audit trail (gitignored)
├── config/default.yml      # rubric weights, thresholds, provider selection
├── STRATEGY.md             # authoritative strategy + roadmap (May 2026 pivot)
└── openspec/
    ├── project.md          # design context (roadmap section superseded by STRATEGY.md)
    ├── AGENTS.md           # OpenSpec workflow
    └── changes/archive/    # completed change proposals (per month)
```

The instance keypair lives outside the repo at
`~/.config/skill-forge/identity/` — back it up; losing it breaks signing.

## Status & roadmap

skill-forge has pivoted from extraction-first to **curation-first**. The
authoritative plan lives in [`STRATEGY.md`](STRATEGY.md).

**Shipped** (all archived under `openspec/changes/archive/`):

| # | Change | What it added |
|---|--------|---------------|
| 1 | add-core-models-and-storage | Pydantic models, filesystem adapter, `ls` / `show` |
| 1b | add-instance-identity | Ed25519 keypair, `origin` + `signature` on every skill |
| 2 | add-extraction-pipeline | `LLMProvider`, fetcher, distiller — `forge extract` |
| 2b | add-import-and-judge | `forge import`, LLM `judge`, `promote` / `demote`, audit trail |
| 3 | add-refinement-loop | `forge refine` with lineage + accept/reject review |
| 4 | add-discovery | `forge discover` / `run` — `gh search` + license heuristic |
| 5 | add-ollama-provider | local LLM via Ollama HTTP |
| 6 | add-plugin-bridges | `forge sync` into consumer tools (symlink/copy) |
| 7 | add-mcp-server-mode | `forge serve mcp` — read-only MCP (stdio/HTTP) |
| 8 | add-federation | `forge peer` — peer-to-peer signed manifest exchange |
| 9 | add-subscribe-and-cite | `forge subscribe` / `check-updates`, source citation |
| 10 | add-import-repo | `forge import-repo` — bulk-import SKILL.md from a GitHub repo |
| 11 | add-release | `forge release` — signed, version-pinned skill bundles |
| 12 | add-skillsets-and-mcp | `tags` + skillsets, `ls --tag` / `forge tags` / `sync --tag`, read-only `forge serve mcp` (stdio) |
| 13 | make-judge-reproducible | median-of-N judging + full judge provenance in the audit trail, `forge judge --explain` |
| 14 | add-advise-mode | read-only `forge advise <slug-or-path>` (skill linter / CI gate); shared `normalize_skill_md` so all import paths accept a vanilla SKILL.md |
| 15 | rubric-v2-structure-examples-tools | judge rubric → 8 axes (+ structural_clarity, example_grounding, tool_declaration); `rubric.version: "2"` |

**Descoped** by the `strip-to-curation-core` change (June 2026): #7
`add-mcp-server-mode` (`serve`), #8 `add-federation` (`peer`), the
`subscribe` half of #9, and #11 `add-release`. skill-forge is a single-user
curated library — the multi-instance distribution machinery (federation,
subscribe, signed release bundles, MCP server) was overhead that did not
serve that use case. The source-citation half of #9 and the local
provenance identity (#1b) stay. The shipped history above is kept for audit.

**MCP later returned** in #12 `add-skillsets-and-mcp`, but narrow: a
read-only, **stdio-only** `forge serve mcp` (three tools) that hands a
*skillset* — live skills carrying a `tag` — to a containerized agent. It is
not the multi-instance HTTP server that was cut; importing, judging, and
promoting stay local.

The live loop now is: `import` → `judge` → `refine`/`lineage` → `promote` →
`sync` (optionally `--tag` for a skillset, or `serve mcp` to hand one to a
container), with provenance tracked end to end.

See [`openspec/project.md`](openspec/project.md) for full design context (note:
its roadmap section is superseded by `STRATEGY.md`) and
[`openspec/AGENTS.md`](openspec/AGENTS.md) for the OpenSpec workflow.

## Known gaps

- **`refine` can time out on large skills.** The default `claude_code.timeout_s`
  (120s) is too short for big bundled skills; bump it in `config/default.yml`.
  (Parked.)

## Development

```bash
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy            # types
```

## License

[EUPL-1.2](LICENSE). Picked for sovereignty framing — `skill-forge` may go open
once it proves broader value.
