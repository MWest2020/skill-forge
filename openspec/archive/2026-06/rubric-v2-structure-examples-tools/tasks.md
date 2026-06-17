# Tasks — rubric-v2-structure-examples-tools

One commit per task, each referencing the change ID. TDD: red test first.

- [x] **1. Axes on the model + weights everywhere.** Extend `JUDGE_AXES`
  (5→8: + `structural_clarity`, `example_grounding`, `tool_declaration`); add
  the 3 fields to `JudgeScore`. Update the 8-axis weights + `rubric.version:
  "2"` in `config.py` DEFAULTS and `config/default.yml`. Fix the hardcoded
  5-axis `_WEIGHTS` in the 5 test files (derive from `JUDGE_AXES` where easy).
  Tests: `JUDGE_AXES` has 8; `JudgeScore` round-trips 8; weights sum to 1.0 and
  cover every axis; existing judge/provider tests stay green.
- [x] **2. Axes in all three judge prompts + tool schema.** Add the 3 axes —
  with the `structural_clarity` vs `schema_compliance` carve-out and the
  `tool_declaration`/`example_grounding` N/A→1.0 rules — to
  `JUDGE_SYSTEM_PROMPT`, claude_code `_JUDGE_PROMPT_HEADER`, ollama
  `_JUDGE_SYSTEM`, and `SCORE_SKILL_TOOL` (properties + `required` + findings
  axis enum). The consistency lock-in test (all axes in all 3 prompts) must
  pass.
- [x] **3. Distiller / refine nudges.** `EXTRACTION_SYSTEM_PROMPT` +
  `REFINEMENT_SYSTEM_PROMPT`: delimit where it aids parsing (avoid over-tagging
  short skills), ground guidance in a compact example, name how to invoke any
  tools. Keep the single-SKILL.md output contract. Test: both prompts mention
  examples + tool invocation.
- [x] **4. Docs.** README: note the rubric is v2 (8 axes; re-judge to refresh a
  score; scores are tagged with their rubric version); add the #15 status row.

## Validate (gate before archive)

- [ ] All tasks checked; specs match code; `ruff`, `mypy --strict`, `pytest`
  green; every file ≤ ~200 lines.
- [ ] Live smoke: `forge judge <a live skill>` produces 8 per-axis scores and
  `forge judge <slug> --explain` shows `rubric version: 2` with all 8 axes in
  the raw runs — no mocks.
