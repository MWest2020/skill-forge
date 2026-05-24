# skill-forge

> Local CLI pipeline that distills sources (URLs, repos, files, chat exports)
> into reusable Anthropic-style **SKILL.md** files — license-aware, LLM-extracted,
> judge-scored, auto-promoted.

## What it is

A personal knowledge pipeline. Examenstof, DevOps patterns, work processes,
component docs — anything currently spread across docs, blog posts, and own
notes — gets one structured form that Claude Code and other agents can mount.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:MWest2020/skill-forge.git
cd skill-forge
uv sync
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

## Quickstart

> The full pipeline lands across changes 1–4 (see roadmap). Today, `ls` and
> `show` work after change #1; the rest raise `NotImplementedError`.

```bash
# List everything in the skills tree (live + draft)
uv run forge ls

# Inspect a single skill
uv run forge show kubernetes-pvc-resize-on-statefulset

# Full pipeline (target shape — works after change #4)
uv run forge run "kubernetes pvc resize"
```

Per-stage commands let you debug each step in isolation:

```bash
uv run forge discover "kubernetes pvc resize"
uv run forge extract https://example.com/post
uv run forge judge skills/_draft/my-skill/SKILL.md
uv run forge promote my-skill
```

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
├── skills/                 # promoted skills (live)
│   └── _draft/             # rejected or pending review (committed for audit)
├── sources/                # provenance per skill
├── runs/                   # JSONL audit trail (gitignored)
├── config/default.yml      # rubric weights + thresholds
├── STRATEGY.md             # authoritative strategy + roadmap (May 2026 pivot)
└── openspec/
    ├── project.md          # design context (roadmap section superseded by STRATEGY.md)
    ├── AGENTS.md           # OpenSpec workflow
    ├── roadmap.md          # stub for changes #6–#8 (plugin bridges, MCP, federation)
    ├── changes/            # active change proposals
    └── archive/            # completed change proposals (per month)
```

## Roadmap

skill-forge has pivoted from extraction-first to **curation-first**. The
authoritative plan lives in [`STRATEGY.md`](STRATEGY.md); a brief shape of
the deferred plugin-bridge / MCP-server / federation work sits in
[`openspec/roadmap.md`](openspec/roadmap.md).

**Done** (archived under `openspec/archive/2026-05/`):

1. **add-core-models-and-storage** — Pydantic models, filesystem adapter, `ls`/`show`.
2. **add-extraction-pipeline** — `LLMProvider` + Anthropic + fetcher + distiller, `forge extract`.
3. **add-claude-code-provider** — subscription auth via `claude -p`, config-driven provider selection.

**Active proposals** (in `openspec/changes/`):

1. **add-instance-identity** — Ed25519 keypair + `origin` + `signature` on every skill.
2. **add-import-and-judge** — `forge import`, real `forge judge`, promote/demote, audit trail.
3. **add-refinement-loop** — `forge refine` with lineage tracking and accept/reject review.

Plus `add-discovery`, `add-ollama-provider`, `add-plugin-bridges`,
`add-mcp-server-mode`, and `add-federation` as outlined in `STRATEGY.md` /
`openspec/roadmap.md`.

See [`openspec/project.md`](openspec/project.md) for full design context (note:
its roadmap section is superseded by `STRATEGY.md`) and
[`openspec/AGENTS.md`](openspec/AGENTS.md) for the OpenSpec workflow.

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
