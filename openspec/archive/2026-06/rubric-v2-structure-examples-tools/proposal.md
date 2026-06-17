# Rubric v2 — structure, examples, tool-declaration axes

## Why

The current 5-axis rubric scores *what* a skill says (clarity, actionability,
coverage) and its provenance, but not three things that materially change how
well an **agent** can consume it:

1. **Structural clarity** — delimited sections (and XML *where it aids
   machine parsing*) help an agent locate the right part. But ceremony hurts:
   a 10-line skill wrapped in tags is worse, not better. No axis rewards
   structure-where-it-helps or penalizes over-tagging.
2. **Example-grounding** — guidance grounded in a concrete worked example is
   more followable than abstract prose. No axis rewards it.
3. **Tool-declaration** — a skill whose procedure invokes tools/commands but
   never says *how* to call them forces the agent to guess. No axis rewards
   naming the invocation.

These are config + prompt in spirit, but honestly they also touch the
`JudgeScore` model, the judge tool-schema, and — critically — they **force a
library-wide re-judge**, because every existing score was produced under the
5-axis rubric (v1). This change owns that ripple explicitly.

## What

- Add three axes: `structural_clarity`, `example_grounding`, `tool_declaration`.
  Wired through `JUDGE_AXES`, the `JudgeScore` model, the `score_skill` tool
  schema, the `JUDGE_SYSTEM_PROMPT`, and `config/default.yml` weights
  (re-summed to 1.0). Bump `rubric.version` → `"2"` (the field added in
  make-judge-reproducible exists for exactly this).
- **Conditional axes score N/A → 1.0.** A tool-less skill is not penalized on
  `tool_declaration`; a pure reference card is not penalized on
  `example_grounding`. The prompt makes "doesn't apply" a pass, so legitimate
  skills aren't gate-blocked (see design for why this beats exempting them from
  the axis floor).
- **`structural_clarity` is carved orthogonal to `schema_compliance`**:
  schema = required sections present + frontmatter valid (does it parse);
  structural = sections delimited *where it helps* + over-tagging penalized.
- Teach the **distiller and refine** prompts to prefer structure-where-it-helps
  and to ground guidance in a referenced/worked example — so newly produced and
  refined skills score well on the new axes. Examples stay out of the top-level
  SKILL.md body where they'd bloat it (respecting the refine-timeout gap);
  referenced or compact inline examples are enough.

## Scope

- `models.py`: 3 new axis fields on `JudgeScore`; extend `JUDGE_AXES`.
- `providers/_prompts.py`: describe the 3 axes in `JUDGE_SYSTEM_PROMPT`
  (incl. N/A→1.0 rules); add them to `SCORE_SKILL_TOOL` properties + required;
  nudge `EXTRACTION_SYSTEM_PROMPT` / `REFINEMENT_SYSTEM_PROMPT` toward
  structure + examples.
- `config/default.yml`: `rubric.version: "2"`; re-weighted 8-axis `weights`.
- Tests: the prompt/tool-schema/model/weights stay mutually consistent
  (`test_judge_prompt_consistency` extends); N/A→1.0 behaviour; weights sum 1.0.

## Out of scope

- **The optional `tools` frontmatter field** (declare tool-dependencies as
  data). The *axis* rewards body prose that names invocation; the *field* is a
  data-model change that belongs with the tier/data work (C) or its own change.
- **Tier and calibration** (#2/#3 — group C).
- **Re-judging the library automatically.** This change makes scores *stale*,
  not wrong; re-judge is operator-driven (`forge judge <slug>`). No auto-demote.

## Risks

- **Axis bloat / double-counting.** `structural_clarity` vs `schema_compliance`
  is the sharp edge — mitigated by the explicit carve-out (design) and the
  consistency test.
- **Conditional axes punishing legitimate skills.** A tool-less or example-less
  skill must not lose its gate on an axis that doesn't apply. Mitigated by
  N/A→1.0 in the prompt (design weighs this vs floor-exemption).
- **Re-judge ripple.** Every live skill's score becomes stale; some may no
  longer clear the gate under v2. We do **not** auto-demote — live stays live;
  `judge`/`advise` surface the v2 view. Documented; operator decides.
- **Prompt/schema/model drift.** Three places must list the same 8 axes — the
  consistency lock-in test guards it; CI fails on drift.
- **Weights are a judgment call.** The design proposes a weighting; it is
  tunable in config without code.
