# Tasks — make-judge-reproducible

One commit per task, each referencing the change ID. TDD: red test first.

- [ ] **1. Models.** Add `JudgeRun` and `JudgeProvenance` to `models.py`; add
  optional `judge_provenance` to `RunEvent`. Tests: construct/validate; axes
  bounded 0–1; round-trip in a RunEvent.
- [x] **2. Provider interface + prompt hash.** `LLMProvider.judge` returns
  `JudgeRun` and takes `temperature=0.0`; added `prompt_sha256` + `parse_judge_axes`
  to `_judge.py` (also de-duplicated the per-provider payload parsing into one
  shared helper). Updated all 3 providers + `FakeProvider`; claude_code documents
  it ignores temperature; anthropic/ollama pass it through (asserted). Dropped
  unused `weights` from the provider signature (total is orchestrator-side).
- [x] **3. Median orchestration.** `judge_skill` runs N times, medians per axis
  (lower-middle for even N), derives total from weights, asserts prompt_sha256 is
  constant across runs, records `JudgeProvenance`. Findings come from the
  lower-median run by total. Landed with #2 for a green tree (coupled). Defaults
  runs=3/temp=0.0/rubric="1" so CLI threading (#4) is decoupled.
- [x] **4. Config wiring.** Added `rubric.version`, `judge.runs`,
  `judge.temperature` to `config/default.yml`; threaded through
  `commands/lifecycle.py judge`; `runs < 1` exits 2 (and `judge_skill` raises).
  Added `audit.latest_event` to read the trail back.
- [x] **5. `judge --explain` + footer.** `--explain` prints the latest judged
  RunEvent's provenance (no re-run; exit 1 if none); normal judge prints the
  `judged N× (median), prompt …, model …` footer; `--runs N` override. CLI tests
  cover explain success + no-record exit 1; orchestrator tests cover median +
  provenance + runs>=1.
- [ ] **6. Docs.** README + `config/default.yml` comments: N×-median, the
  claude_code temperature caveat, and that "auditable/re-checkable" ≠ bit-exact.

## Validate (gate before archive)

- [ ] All tasks checked; specs match code; `ruff`, `mypy --strict`, `pytest`
  green; every file ≤ ~200 lines.
- [ ] Live smoke: `forge judge <a live skill>` records provenance; `forge judge
  <slug> --explain` prints it with all reproducibility fields, no mocks.
