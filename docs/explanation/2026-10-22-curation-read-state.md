---
status: current
last_reviewed: 2026-10-22
---

# Curation decision 2026-10-22: read-state

Made for the agent factory in ratatoskr (change `odin-runs-the-factory`, phase
4). Mark, 2026-10-22: *"factory pattern should be agent -> skills -> tool
usage. clearly defined."* A role's tools are derived from its skills, so a
capability that needs a tool has to be a skill.

## Promoted (in this PR)

| Skill | Score | Decision |
|---|---|---|
| read-state | 0.92 | **live**. It fills a gap with direct use: odin's read shell (ratatoskr `agents/readshell.py`) as a skill. `allowed-tools: Bash(python3 agents/readshell.py:*)` is the only tool it adds, and the handbook derives odin's Bash rule from it. |

It was judged three times, 3× per round with the per-axis median and rubric
v2:

1. **0.89**, with two warnings: no working directory, and no example.
2. **0.89**, with two warnings: the sections were in the wrong order, and the
   example embellished a check name ("the docs gate" for `gates / gates`).
3. **0.92**, with no warnings left.

The draft was re-imported each time instead of edited, because drafts are
signed.

## Also in this PR

The register gains `tools` per skill (change `register-carries-tools`), from
`allowed-tools`, and an empty list when a skill declares none. All 46 other
live skills declare none, so they add no tools to any role.
