# Spec — judge

Lives at `src/skill_forge/evaluation/judge.py`. The judge runs the rubric
against an existing skill and produces (a) a `JudgeScore` and (b) per-axis
`JudgeFinding`s the user (and future refinement loop) can act on.

## New model: `JudgeFinding`

```python
class JudgeFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    axis: str                                       # one of JUDGE_AXES
    observation: str                                # 1–3 sentences
    severity: Literal["info", "warning", "blocker"]
```

`axis` must be one of `JUDGE_AXES` (from `models.py`). Findings are typed by
severity so refinement can prioritise blockers first.

## Provider extension

```python
class LLMProvider(ABC):
    @abstractmethod
    def judge(self, skill: Skill) -> tuple[JudgeScore, list[JudgeFinding]]:
        """Score `skill` against the rubric. Findings explain lost points."""
```

Both `AnthropicProvider` and `ClaudeCodeProvider` implement it.

- **AnthropicProvider.judge**: a single `messages.create` call with a
  `score_skill` tool whose input_schema mirrors `{schema_compliance,
  clarity, actionability, gap_coverage, provenance_quality, findings}`.
  `tool_choice={"type": "tool", "name": "score_skill"}` forces structured
  output. The `total` is computed client-side from the configured weights
  rather than asked of the model — eliminates "model says 0.87 but the
  weighted sum is 0.62" drift.
- **ClaudeCodeProvider.judge**: `claude -p` with the same JSON-only
  prompt pattern as `extract_draft`, returning the same shape.

The judge system prompt lives in `providers/_prompts.py` (new section).
It includes the rubric weights inline so the model can self-calibrate.

## Orchestration

```python
def judge_skill(
    root: Path,
    slug: str,
    *,
    provider: LLMProvider,
    weights: dict[str, float],
    identity: Identity | None = None,
) -> JudgeScore: ...
```

1. `storage.read_skill(root, slug, identity=identity)` — strict-load.
2. `provider.judge(skill)` → `(per_axis, findings)`.
3. Compute `total` from per_axis × weights. Validate via `JudgeScore.model_validate(..., context={"weights": weights})`.
4. Append `RunSummary(run_id, judge_score=total, promoted=False)` to
   `sources/{slug}.yml` runs list.
5. Append a `Run` event (`event="judged"`, `scores=<JudgeScore>`,
   `skill_slug=<slug>`) to `runs/{run_id}.jsonl`.
6. Return the `JudgeScore` (caller prints / acts on it).

## CLI

```
forge judge <slug> [--root PATH]
```

Output (rich table or plain — TBD during Apply):

```
Judging: kubernetes-pvc-resize-on-statefulset
  schema_compliance   0.92  ✓
  clarity             0.85  ✓
  actionability       0.78  ✓
  gap_coverage        0.55  ✗  (axis_min 0.50 — passes by 5%)
  provenance_quality  0.40  ✗  (below axis_min 0.50)
  ───────────────────────────
  total               0.69  (below total_min 0.75)

Findings:
  [blocker] provenance_quality: Only one source listed, no SHA256 captured.
  [warning] gap_coverage: Overlaps significantly with existing kubernetes-pvc-resize.
  [info]    actionability: Step 3 is vague — consider citing exact kubectl flag.

Result: stays in draft (below total threshold).
```

Exit codes: `0` ok regardless of pass/fail (the score IS the answer), `1`
on fetch/parse/provider failure, `2` on identity issue.

## Out of scope

- Bulk re-judging (`forge judge --all`). Easy follow-up.
- Auto-promote on judge success (the user runs `forge promote` explicitly).
- Judge prompt versioning / A-B testing. Pin the prompt + model in
  `config/default.yml`; rejudging is cheap if scores need recalibrating.
