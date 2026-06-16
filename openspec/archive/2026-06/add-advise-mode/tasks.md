# Tasks — add-advise-mode

One commit per task, each referencing the change ID. TDD: red test first.

- [ ] **1. Factor out `score_skill` (no I/O).** Extract the N-run + per-axis
  median + provenance assembly from `judge_skill` into
  `score_skill(skill, *, provider, weights, runs, temperature, rubric_version)
  -> (JudgeScore, findings, JudgeProvenance)`. `judge_skill` becomes
  `score_skill` + persist (audit + run summary), signature and side effects
  unchanged. The `runs >= 1` guard moves to `score_skill`. Tests: existing judge
  tests stay green; `score_skill` writes nothing (tree unchanged) and returns
  provenance.
- [ ] **2. Share the normalizer.** Lift `_normalize_external_skill_md` from
  `import_skill/repo.py` into a shared `import_skill` helper; `repo.py` uses it;
  wire `import` and `import-dir` to normalize a vanilla SKILL.md too (closes the
  known gap). Test: import a bare `name`+`description` skill via `import`,
  `import-dir`, and `import-repo` — all land a valid normalized skill.
- [x] **3. `forge advise` command.** `commands/advise.py`: path wins if the
  file exists (normalized in memory) else slug; calls `score_skill` (never
  `judge_skill`); prints per-axis + strengths + weaknesses&fixes + verdict.
  `--runs<1` exits 2, missing target exits 1. CLI tests cover slug, raw path,
  read-only (tree unchanged), and both exit codes.
- [x] **4. Docs.** README documents `forge advise` (linter / CI gate), adds the
  #14 row, and removes the now-closed normalize known gap (refine-timeout gap
  kept, marked parked).

## Validate (gate before archive)

- [ ] All tasks checked; specs match code; `ruff`, `mypy --strict`, `pytest`
  green; every file ≤ ~200 lines.
- [ ] Live smoke: `forge advise <a raw SKILL.md path>` on a real un-imported
  file prints advice and writes nothing (verify `git status` clean), no mocks.
