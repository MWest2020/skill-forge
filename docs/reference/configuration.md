---
status: draft
last_reviewed: 2026-07-13
---

# Reference: configuration & CLI

Facts about how skill-forge is configured and invoked. Distilled from the
README and [`openspec/project.md`](../../openspec/project.md); verify against the
shipped `config/default.yml` when in doubt.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management (never `pip`
  directly)

```bash
uv sync            # install
uv run forge ...   # run any command
```

## Configuration file

Defaults live in `config/default.yml`. Override per project via
`config/local.yml` (which the local overlay merges on top of the defaults).

| Section | Key | Default | Meaning |
|---|---|---|---|
| `rubric` | `version` | `"2"` | Rubric version; recorded in every judge's provenance so a score is tied to the rubric it was produced under. |
| `rubric.weights` | 8 axes | see below | Per-axis weights; must sum to 1.0. |
| `promotion` | `total_min` | `0.75` | Minimum total score to promote to live. |
| `promotion` | `axis_min` | `0.50` | Minimum per-axis score to promote. |
| `judge` | `runs` | `3` | Score N times and take the per-axis median (tames LLM non-determinism); `1` disables median. |
| `judge` | `temperature` | `0.0` | Honored by `anthropic`/`ollama`; the `claude_code` provider has no temperature flag. |
| `providers` | `extract`, `judge` | `claude_code` | Which provider runs each stage. |
| `discovery` | `max_candidates` | `10` | Cap on discovery candidates. |
| `discovery` | `respect_robots_txt` | `true` | Honor robots.txt during discovery. |
| `paths` | `skills`, `drafts`, `sources`, `runs` | see file | Storage paths, relative to project root. |

### Rubric axes (rubric v2)

Each axis scores 0.0 – 1.0; the weighted sum is the total.

| Axis | Weight |
|---|---|
| `actionability` | 0.22 |
| `clarity` | 0.15 |
| `gap_coverage` | 0.15 |
| `schema_compliance` | 0.12 |
| `provenance_quality` | 0.12 |
| `structural_clarity` | 0.10 |
| `example_grounding` | 0.08 |
| `tool_declaration` | 0.06 |

## Providers

Selected per pipeline stage under `providers`:

- **`claude_code`** (default) — uses your Claude Code subscription via the
  `claude -p` binary; no API key required.
- **`anthropic`** — uses `ANTHROPIC_API_KEY` (pay-per-token; supports forced
  tool use). Set the model under the `anthropic` section.
- **`ollama`** — local LLM over HTTP; falls back to `$OLLAMA_HOST`, then
  `http://localhost:11434`.

## CLI surface

The full command tour lives in the [README](../../README.md#quickstart). The
core curation loop:

```
import → judge → refine / lineage → promote → sync
```

Common commands:

- `forge import-repo <url>` / `forge import <path>` — intake SKILL.md files
  (all import paths normalize a vanilla Anthropic skill).
- `forge ls` / `forge show <slug>` — list and inspect skills.
- `forge judge <slug>` — score a draft against the rubric (`--explain` shows
  recorded provenance).
- `forge advise <slug-or-path>` — read-only verdict, no writes (CI gate).
- `forge promote <slug>` / `forge demote <slug>` — move between live and draft.
- `forge refine <slug>` / `forge diff <slug>` / `forge refine-accept <slug>` —
  the refinement loop.
- `forge tier <slug>` / `forge gold <slug>` / `forge calibrate` — derived trust
  tiers.
- `forge sync <target>` — mount live skills into a consumer tool
  (`--tag <t>` for a skillset).

## Known gaps

- `refine` can time out on large skills. The default `claude_code.timeout_s`
  (120s) is too short for big bundled skills; raise it in `config/local.yml`.
