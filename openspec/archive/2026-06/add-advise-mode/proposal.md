# Add advise-mode (read-only judge + skill linter)

## Why

The judge is already the quality signal, but today it only runs on **imported**
skills and it **writes** (audit event + run summary). Two gaps:

1. You can't get a verdict on a SKILL.md you haven't adopted yet — so the judge
   can't act as a *linter* in a CI gate (e.g. a Hydra/agentic quality gate that
   blocks a skill below threshold before it's ever imported).
2. "Just tell me how good this is" shouldn't mutate state.

`forge advise` closes both: a read-only judge that accepts a raw filesystem path
*or* an imported slug, prints structured advice, and writes nothing. It's the
cheapest possible win on top of `make-judge-reproducible` — same median-of-N
judge, no new scoring logic.

## What

- **`forge advise <slug-or-path>`** — resolve the target:
  - an imported **slug** → read the live/draft skill (no identity check; advice
    is read-only and never promotes);
  - a **filesystem path** to a SKILL.md → read + normalize it in memory (the
    same normalization `import-repo` applies to a vanilla `name`+`description`
    skill), so an un-adopted skill can be linted without importing it.
- Run the existing median-of-N judge and print **structured advice**: per-axis
  score with a pass/fail mark, **strengths** (axes that clear the bar with no
  findings), **weaknesses + fixes** (the judge's findings, which already name
  what lost points), and the overall verdict against the promotion threshold.
- **Writes nothing**: no promote, no `runs/` event, no `sources.yml` update, no
  files placed. Read-only is a contract, tested.

## Scope

- `evaluation/judge.py`: factor the score-N-times-and-median logic into a pure
  `score_skill(skill, *, provider, weights, runs, temperature, rubric_version)
  -> (JudgeScore, findings, JudgeProvenance)` with **no I/O**. `judge_skill`
  becomes `score_skill` + persist (audit + run summary) — behaviour unchanged.
- `import_skill/`: lift `_normalize_external_skill_md` (currently private to
  `repo.py`) into a shared helper so `advise` (and, as a side-benefit, `import`
  / `import-dir`) can normalize a vanilla SKILL.md the same way. Closes the
  long-standing "only import-repo normalizes" known gap.
- `commands/`: a new `advise` command that calls `score_skill` (never
  `judge_skill`) and formats the advice. No new interface — reuses the existing
  `LLMProvider`; the convention stays `providers/base.py` (no `protocols.py`).

## Out of scope

- Any state mutation (promote/write/audit) from `advise`.
- Changing the rubric axes or weights (that's the rubric-v2 change).
- Generating fixes via a *separate* LLM call — the judge's findings are the
  advice; richer rewrites are what `refine` is for.
- Fixing the `import`/`import-dir` *strictness* beyond normalization (the
  refine-timeout known gap is unrelated and stays parked).

## Risks

- **advise-on-path depends on shared normalization.** Folded into this change
  (the `_normalize_external_skill_md` lift). Without it, a vanilla SKILL.md
  fails the strict parser. Tested: advise a bare `name`+`description` skill from
  a path.
- **Read-only must be real, not assumed.** Mitigation: a test asserts the tree
  is byte-for-byte unchanged after `advise` (same pattern as the MCP read-only
  test), and `advise` calls `score_skill`, which has no I/O by construction.
- **Refactor regression.** Splitting `score_skill` out of `judge_skill` could
  change judge behaviour. Mitigation: the existing judge tests must stay green
  unchanged; `judge_skill` keeps its signature and side effects.
- **N× cost on a CI gate.** advise runs the judge N times like the gate; a CI
  caller can pass `--runs 1` for speed. Documented.
