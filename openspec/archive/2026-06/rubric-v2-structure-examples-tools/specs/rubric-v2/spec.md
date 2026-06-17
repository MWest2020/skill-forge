# Spec — rubric v2 (8 axes)

## Axes

The rubric scores **eight** axes, each 0.0–1.0. The five v1 axes are unchanged
in meaning. The three new axes:

### `structural_clarity`

Given the expected sections exist (that's `schema_compliance`), is the content
*shaped* so an agent can locate and extract the right part — without ceremony?

- **Rewards:** labelled/numbered steps in a long procedure; fenced or tagged
  blocks around content meant to be used verbatim (commands, payloads, config);
  delimiters that aid extraction.
- **Penalizes (over-tagging):** XML/section scaffolding on a short skill, nested
  wrappers that add no extraction value. A compact skill with no tags may score
  1.0; ceremony scores low.
- Orthogonal to `schema_compliance` (presence/validity of sections) — see
  `design.md` §1.

### `example_grounding`

Is the guidance grounded in a concrete worked example rather than pure
abstraction? A compact inline example or a clear reference suffices; large
examples need not live in the SKILL.md body.

- **N/A → 1.0:** a pure reference/lookup card that needs no worked example
  scores 1.0 (not penalized for lacking one it doesn't need).

### `tool_declaration`

If the procedure invokes tools/commands, does it name **how** to call them
(invocation, key flags, where output goes)? skill-forge does not own or
generate the tools — the skill points at them.

- **N/A → 1.0:** a skill whose procedure invokes no external tool scores 1.0.

## Scoring contract

- The judge emits all eight per-axis floats via `score_skill`; the **total**
  remains caller-computed from the configured weights (unchanged mechanism).
- `JUDGE_AXES`, the `JudgeScore` fields, the `score_skill` tool properties +
  `required`, and the `JUDGE_SYSTEM_PROMPT` axis list MUST name the same eight
  axes. The consistency lock-in test enforces this; CI fails on drift.
- Non-applicable conditional axes (`tool_declaration`, `example_grounding`)
  score **1.0**, per the prompt — keeping the per-axis promotion floor uniform
  across all eight axes (no floor exemption; `promoter` is unchanged).

## Config

```
rubric:
  version: "2"          # was "1"; recorded in every judge's provenance
  weights:              # must sum to 1.0
    actionability:      0.22
    clarity:            0.15
    gap_coverage:       0.15
    schema_compliance:  0.12
    provenance_quality: 0.12
    structural_clarity: 0.10
    example_grounding:  0.08
    tool_declaration:   0.06
```

Weights are tunable without code; the loader still requires every `JUDGE_AXES`
key to be present in `weights` (missing key → clear error, as today).

## Distiller / refine guidance

`EXTRACTION_SYSTEM_PROMPT` and `REFINEMENT_SYSTEM_PROMPT` gain guidance to:
- delimit content where it aids parsing (fence/tag verbatim-use blocks) **and**
  avoid over-tagging short skills;
- ground guidance in a concrete example where one adds value, kept compact;
- name how to invoke any tools/commands the procedure uses.

This makes produced/refined skills score well on the new axes without changing
the output *format* contract (still a single SKILL.md body).

## Versioning & migration

- Bumping to `"2"` makes existing recorded scores v1 artifacts. Scores are
  **stale, not wrong**; no automatic re-judge, no auto-demote (design §4).
- Every judge call records `rubric_version`, so v1 and v2 scores are
  distinguishable in `runs/*.jsonl` and via `forge judge --explain`.

## Non-goals

- No `tools` frontmatter field (deferred).
- No bulk re-judge / calibration (group C).
- No new example-file management; the axis judges the body as written.
