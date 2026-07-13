---
status: draft
last_reviewed: 2026-07-13
---

# skill-forge

skill-forge is a local, single-user CLI pipeline that curates an owned library
of Anthropic-style **SKILL.md** files: import from anywhere, score against a
rubric, refine across iterations, derive trust tiers, and mount the result into
the agent tools you use — license-aware and provenance-tracked end to end.

**Status:** active. This `docs/` tree is newly seeded and its pages are
`draft` until a content review promotes them to `current`.

## Start here

- [README](../README.md) — install, quickstart, and the full command tour.
  `docs/` points at the README; it does not replace it.
- [STRATEGY.md](../STRATEGY.md) — authoritative strategy and roadmap
  (curation-first pivot, May 2026).

## Sections

- [Reference](reference/configuration.md) — configuration and the CLI surface
  (`config/default.yml`, provider selection, pipeline stages).

Design context lives in [`openspec/project.md`](../openspec/project.md) (note:
its roadmap section is superseded by `STRATEGY.md`) and the OpenSpec workflow in
[`openspec/AGENTS.md`](../openspec/AGENTS.md).
