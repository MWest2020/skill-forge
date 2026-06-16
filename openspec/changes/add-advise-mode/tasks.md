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
- [ ] **3. `forge advise` command.** Resolve `<target>` as a path (if the file
  exists) else a slug; for a path, read + normalize in memory; call
  `score_skill` (never `judge_skill`); format advice (per-axis + strengths +
  weaknesses&fixes + verdict). `--runs` override; `--runs < 1` exits 2; missing
  target exits 1. Tests via `CliRunner`: advise an imported slug; advise a raw
  vanilla SKILL.md from a path; read-only (tree byte-for-byte unchanged); exit
  codes.
- [ ] **4. Docs.** README: `forge advise` as a read-only linter / CI quality
  gate (path input, `--runs 1` for speed); add the #14 status row.

## Validate (gate before archive)

- [ ] All tasks checked; specs match code; `ruff`, `mypy --strict`, `pytest`
  green; every file ≤ ~200 lines.
- [ ] Live smoke: `forge advise <a raw SKILL.md path>` on a real un-imported
  file prints advice and writes nothing (verify `git status` clean), no mocks.
