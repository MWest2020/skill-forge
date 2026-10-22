# The register carries each skill's tools

## Why

Mark, 2026-10-22, about the agent factory in ratatoskr and the handbook:
*"factory pattern should be agent -> skills -> tool usage. clearly defined."*

A role in the handbook declares skills and tools side by side, and nothing ties
them together. The handbook can only check that a role's tools are exactly what
its skills need if it knows what each skill needs. The register (`forge
register`) is how the handbook knows a skill exists, so it is also the place to
say which tools the skill uses.

`SKILL.md` already has the field: `allowed-tools`, which Claude Code itself
enforces. The Skill model reads it (`allowed_tools`). The register drops it.

## What changes

- **Every register entry gains `tools`:** the skill's `allowed-tools` as a
  list, or `[]` when it declares none. An empty list means the skill needs
  nothing beyond what every agent has.
- **`version` stays 1.** A consumer that ignores `tools` is unaffected.
