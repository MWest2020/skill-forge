# Spec — reproducible judge + provenance

## Models

`JudgeRun` — the result of one provider judge call:

```
axes: dict[str, float]      # per-axis 0.0–1.0 (no total; total is derived)
findings: list[JudgeFinding]
model_id: str               # e.g. "anthropic:claude-opus-4-7", "claude_code:claude"
prompt_sha256: str          # sha256 of the exact prompt string sent
```

`JudgeProvenance` — recorded once per `judge_skill` call:

```
provider: str               # "anthropic" | "claude_code" | "ollama"
model_id: str
rubric_version: str         # from config rubric.version
prompt_sha256: str          # the prompt is identical across the N runs
temperature: float          # requested; advisory for claude_code
runs: int                   # N
raw_axes: list[dict[str, float]]   # each run's per-axis scores, in call order
median_axes: dict[str, float]      # the reduced per-axis scores
```

`RunEvent` gains an optional `judge_provenance: JudgeProvenance | None = None`
(present on `event == "judged"`).

## Provider interface (`LLMProvider`, in `providers/base.py`)

```
judge(skill, *, weights, temperature: float = 0.0) -> JudgeRun
```

- Builds the judge prompt, computes `prompt_sha256` over the exact string sent,
  reports `model_id`, and applies `temperature` where the backend supports it.
- `claude_code` ignores `temperature` (the `claude -p` CLI has no such flag) but
  still returns the value it was asked for via the orchestrator's record. This
  is documented in the provider docstring.
- `findings` and per-axis `axes` are returned; the **total is not** — it is
  always derived client-side from `weights`, unchanged from today.

## Orchestration (`evaluation/judge.py`)

`judge_skill(root, slug, *, provider, weights, runs, temperature, rubric_version, identity)`:

1. Read the skill (strict if identity given), as today.
2. Call `provider.judge(skill, weights=weights, temperature=temperature)` `runs`
   times. All runs use the same prompt, so `prompt_sha256` is constant; assert it.
3. **Median per axis:** for each axis, sort the `runs` values and take the
   median. For even `runs`, take the **lower-middle** value (conservative for a
   gate — never inflates a borderline score). Single run → that run.
4. Build the final `JudgeScore` from `median_axes` + `weights`
   (`build_judge_score`), so `total` matches the weighted median exactly.
5. Findings: keep the findings from the run whose `total` equals the median
   total (first such run); they explain the score that actually gates.
6. Append a `RunEvent(event="judged", scores=<final>, findings=<chosen>,
   judge_provenance=JudgeProvenance(...))` and the `RunSummary` as today.

`runs` defaults and `temperature` come from config (below); callers may override.

## Config (`config/default.yml`)

```
rubric:
  version: "1"          # bump when axes/weights/prompt change; recorded per judge
  weights: { ... }      # unchanged
judge:
  runs: 3               # N; >=1
  temperature: 0.0
```

`judge.runs` must be `>= 1`; invalid config is a clear startup error.

## CLI

### `forge judge <slug> [--explain] [--runs N] [...]`

- Without `--explain`: judge as above; print the score breakdown as today, plus
  a one-line footer `judged N× (median), prompt <sha256[:12]>, model <model_id>`.
- `--explain`: do **not** re-run the judge. Read the latest `event == "judged"`
  `RunEvent` for `<slug>` from `runs/*.jsonl` and print its `judge_provenance`:
  provider, model, rubric version, prompt sha256, temperature, N, each raw run's
  axes, and the median. If no judged record exists: `no judged record for
  <slug>; run \`forge judge <slug>\` first.` (exit 1).
- `--runs N`: override `judge.runs` for this call.

## Non-goals

- No bit-exact reproducibility; the record supports *re-checking*, not replay.
- Rubric axes/weights unchanged (only a `version` string is added).
