# Tasks — make-judge-reproducible

One commit per task, each referencing the change ID. TDD: red test first.

- [ ] **1. Models.** Add `JudgeRun` and `JudgeProvenance` to `models.py`; add
  optional `judge_provenance` to `RunEvent`. Tests: construct/validate; axes
  bounded 0–1; round-trip in a RunEvent.
- [ ] **2. Provider interface + prompt hash.** `LLMProvider.judge` returns
  `JudgeRun` and takes `temperature=0.0`; add `prompt_sha256` helper in
  `_judge.py`. Update `anthropic`, `ollama`, `claude_code` (claude_code documents
  that it ignores temperature) and the test `FakeProvider`. Tests: each provider
  returns a `JudgeRun` with model_id + non-empty prompt_sha256; anthropic/ollama
  pass temperature through (assert via a stub).
- [ ] **3. Median orchestration.** `judge_skill` runs N times, medians per axis
  (lower-middle for even N), derives total from weights, records
  `JudgeProvenance`. Tests: 3 stubbed runs → median axis values; even-N picks
  lower-middle; prompt_sha256 constant across runs (asserted); provenance fields
  all populated.
- [ ] **4. Config wiring.** Add `rubric.version`, `judge.runs`, `judge.temperature`
  to `config/default.yml`; thread through `cli`/`commands/lifecycle.py`;
  validate `runs >= 1`. Test: config defaults load; `runs < 1` errors.
- [ ] **5. `judge --explain` + footer.** `--explain` prints the latest judged
  RunEvent's provenance (no re-run; exit 1 if none); normal judge prints the
  median/prompt/model footer; `--runs N` override. Tests via `CliRunner`.
- [ ] **6. Docs.** README + `config/default.yml` comments: N×-median, the
  claude_code temperature caveat, and that "auditable/re-checkable" ≠ bit-exact.

## Validate (gate before archive)

- [ ] All tasks checked; specs match code; `ruff`, `mypy --strict`, `pytest`
  green; every file ≤ ~200 lines.
- [ ] Live smoke: `forge judge <a live skill>` records provenance; `forge judge
  <slug> --explain` prints it with all reproducibility fields, no mocks.
