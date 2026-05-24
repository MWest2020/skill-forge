# skill-forge — project context

## One-line pitch

A local CLI pipeline that turns sources (URLs, repos, files, chat exports) into
reusable Anthropic-style **SKILL.md** files, with license-aware discovery,
LLM-based extraction, judge-based scoring, and auto-promotion to a `skills/`
directory that agents can mount.

## Purpose

Personal knowledge pipeline. Examstof, DevOps-patterns, work processes, Hydra
components — anything currently spread across docs, blog posts, and own notes —
gets one structured form that Claude Code (and Hydra containers) can consume.

## Non-goals

- No scraping of sources that forbid it (paywalled, robots.txt disallow,
  explicit ToS against automated access).
- No redistribution of scraped content. Output is always paraphrased via LLM,
  with source attribution.
- No multi-user, no cloud sync, no web UI in MVP.
- No flashcard export, no exam-question reproduction.

## License-awareness (hard requirement)

Every source is classified before extraction:

| Class | Treatment |
|---|---|
| Permissive (MIT, Apache-2.0, CC-BY, public domain) | Extract + attribute |
| Copyleft (GPL, AGPL, CC-BY-SA) | Extract + attribute + share-alike note |
| Restrictive (CC-BY-NC, proprietary with explicit permission) | Extract for personal use only, do not share |
| Forbidden (ToS forbids automated access, noindex without clear license, paywall) | Skip, log to `discovery_blocked.log` |

Discovery must detect license before fetch — via metadata where possible, else
heuristics + human flag.

## Tech conventions (Mark-defaults)

- Python 3.12+.
- `uv` for dependency management — never `pip` directly.
- Max ~200 lines per file. Split earlier rather than later.
- Boring & auditable: stdlib where possible.
- CLI via `typer`.
- Data lives in flat files (`skills/`, `sources/`, `runs/`). Git is the database.
- No external DB, no Redis, no queue server. MVP is synchronous, one skill at a time.
- Logging via stdlib `logging`, JSON output to `runs/*.jsonl` for audit trail.
- Tests: `pytest`. Lint/format: `ruff`. Types: `mypy --strict` on `src/`.
- LLM providers modular: `providers/anthropic.py`, `providers/ollama.py` behind a
  common `LLMProvider` base. Anthropic first; Ollama for the judge stage where
  latency and cost matter.
- API keys via `.env` (not committed) or env vars.

## Repo layout

```
skill-forge/
├── pyproject.toml          # uv-managed
├── README.md
├── .env.example
├── .gitignore
├── openspec/
│   ├── project.md          # this file
│   ├── AGENTS.md           # OpenSpec workflow conventions
│   └── changes/            # change proposals
├── src/skill_forge/
│   ├── cli.py              # typer entrypoint
│   ├── models.py           # Skill, Source, Run, JudgeScore
│   ├── discovery/          # web + github search, license_check
│   ├── extraction/         # fetcher + distiller
│   ├── evaluation/         # judge
│   ├── promotion/          # promoter
│   ├── providers/          # anthropic, ollama (LLMProvider base)
│   └── storage/            # filesystem adapter
├── skills/                 # promoted skills (live)
│   └── _draft/             # rejected or pending review
├── sources/                # provenance per skill
├── runs/                   # JSONL audit trail per pipeline run (gitignored)
├── config/default.yml      # rubric weights, thresholds, providers
└── tests/
```

## SKILL.md schema

Anthropic SKILL.md convention with frontmatter:

```markdown
---
name: kubernetes-pvc-resize-on-statefulset
description: Use this skill when resizing a PVC bound to a StatefulSet on a CSI driver that supports volume expansion. Covers the patch sequence, pod restart requirement, and common failure modes.
version: 1
sources:
  - id: src-a1b2c3
  - id: src-d4e5f6
judge_score: 0.87
created: 2026-05-24
---

# Resize PVC on StatefulSet

## When to use
...

## Procedure
...

## Failure modes
...
```

Per skill, `sources/{slug}.yml` carries provenance (URL, license, fetched_at,
sha256, contribution note) and a `runs` history with judge scores.

## Judge rubric (configurable via `config/default.yml`)

Score 0.0 – 1.0 on five axes:

- `schema_compliance` (0.20) — valid frontmatter, expected sections
- `clarity` (0.20) — clear "when to use", no unexplained jargon
- `actionability` (0.25) — an agent can follow this, not just read it
- `gap_coverage` (0.20) — adds something versus existing skills
- `provenance_quality` (0.15) — sources clear, license correct, no gaps

Promotion threshold: total ≥ 0.75 **and** every axis ≥ 0.50. Configurable.

## Pipeline flow

```
topic -> discovery -> [candidates]
                   -> license_check -> [allowed sources]
                   -> fetcher -> [raw content]
                   -> distiller (Claude) -> draft SKILL.md
                   -> judge (Claude or Ollama) -> judge_score
                   -> IF score >= threshold:
                         promote -> skills/{slug}/
                      ELSE:
                         skills/_draft/{slug}/ + review reason
                   -> audit log -> runs/{run_id}.jsonl
```

Each step is a separate CLI command **and** subroutine, so you can run them in
isolation for debugging.

## CLI commands (MVP)

- `forge discover <topic>` — find + license-filter, list candidates only
- `forge extract <source_url>` — extraction only, draft SKILL.md output
- `forge judge <skill_path>` — judge only, score + breakdown
- `forge run <topic>` — full pipeline
- `forge promote <slug>` — manual promotion (overrules threshold)
- `forge demote <slug>` — manual demotion with a reason
- `forge ls` — list skills (live + draft) with scores
- `forge show <slug>` — show SKILL.md + sources.yml

## Roadmap (change proposals)

1. **add-core-models-and-storage** — Pydantic models, filesystem adapter, `ls` and `show` working. No LLM, no network. (Active.)
2. **add-extraction-pipeline** — `LLMProvider` base + Anthropic implementation, fetcher (robots.txt aware), distiller, `extract <url>` working.
3. **add-judge-and-promotion** — judge with configurable rubric, promoter with threshold check, audit trail to `runs/*.jsonl`.
4. **add-discovery** — web + GitHub search, license detection, `discover <topic>` and end-to-end `run <topic>`.
5. **add-ollama-provider** — Ollama implementation of `LLMProvider`, config switch per stage.
6. **add-refinement-loop** (later) — existing skill + new source -> merge proposal, conflict resolution.

The current scope is changes 1 – 5. Change 6 is intentionally out of MVP.

## Disclaimer

> `skill-forge` distills public sources into reusable SKILL.md files. The tool
> respects source licenses, paraphrases content via LLM (no verbatim
> reproduction), and logs provenance per skill. Sources under restrictive
> licenses or whose ToS forbids automated access are not processed. Output is
> intended for personal and/or internal use; redistribution depends on source
> license.
