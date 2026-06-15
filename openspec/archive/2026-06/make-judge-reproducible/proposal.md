# Make the judge reproducible

## Why

The judge is the gate: a skill promotes only at `total ≥ 0.75` with every axis
`≥ 0.50`. But LLM-as-judge is non-deterministic — a re-judge can drift across
the threshold, turning the gate into a dice roll. That directly contradicts the
provenance/auditability premise: a score you can't explain or re-check is not a
gate. (We saw the drift first-hand: maintainability-review judged 0.95 then 0.93
on re-run, owasp 0.87 then 0.88.)

This change does **not** chase bit-exact reproducibility — impossible with hosted
LLMs that drift across model versions and don't guarantee determinism. It makes
each score **variance-bounded and auditable**: scored N times and reduced by
median, with a full provenance record so the score can be re-checked from pinned
inputs and explained in an ISO-27001 context.

## What

- **Score N times, take the median per axis.** N defaults to 3, configurable at
  `judge.runs` in `config/default.yml`. The total is recomputed from the median
  axes and the rubric weights (as today, client-side).
- **Temperature 0 where the provider supports it.** `anthropic` and `ollama`
  honor `judge.temperature` (default 0.0); the default `claude_code` provider
  calls `claude -p`, which exposes no temperature flag — the requested value is
  still recorded, but for that provider median-of-N is the determinism lever,
  not temperature. This limitation is documented, not hidden.
- **Persist judge provenance** in the `runs/*.jsonl` audit trail for every judge
  call: provider, model identifier, rubric version, sha256 of the exact prompt
  sent, temperature, N, each raw run's per-axis scores, and the resulting
  median. A score is re-derivable from this record (modulo model drift).
- **`forge judge --explain <slug>`** prints the recorded provenance for the
  latest judged score, without re-running the judge.

## Scope

- `models.py`: a `JudgeRun` (one provider call: axes, findings, model_id,
  prompt_sha256) and a `JudgeProvenance` record; `RunEvent` gains an optional
  `judge_provenance`.
- `providers/base.py` + `_judge.py`: `judge()` returns `JudgeRun` and takes
  `temperature`; a shared `prompt_sha256` helper. Interface stays in `base.py`
  (the project's interface convention — there is no `protocols.py`).
- `providers/{anthropic,ollama,claude_code}.py`: build prompt, hash it, report
  model_id, honor temperature where possible.
- `evaluation/judge.py`: N-run loop + per-axis median + provenance assembly.
- `config/default.yml`: `rubric.version`, `judge.runs`, `judge.temperature`.
- `cli.py`/`commands/lifecycle.py`: thread the config; `judge --explain`.

## Out of scope

- Changing the rubric axes or weights.
- Bit-exact reproducibility / pinning model weights (not achievable on hosted
  providers — see Why).
- Caching or skipping re-judges.

## Risks

- **N× cost/latency.** Default 3 triples judge calls. Acceptable for a gate;
  documented, and configurable down to 1 for cheap iteration.
- **Overclaiming "reproducible".** Mitigated by framing: the record makes a score
  *auditable and re-checkable*, not bit-exact. Spec and `--explain` output say so.
- **Interface churn.** `judge()` return type changes, touching 3 providers + the
  test fakes. Mechanical, covered by existing provider tests.
- **Even N → median of two middle values.** Define median as the lower-middle
  (conservative for a gate) or average; spec pins the rule.
