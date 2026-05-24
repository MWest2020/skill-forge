# Spec — refine

`forge refine <slug>` takes a skill plus its latest judge findings and
produces a new iteration. Non-destructive: the current `SKILL.md` is
unchanged until `refine-accept` is run.

## Provider extension

```python
class LLMProvider(ABC):
    @abstractmethod
    def refine(
        self,
        skill: Skill,
        *,
        findings: list[JudgeFinding],
        hint: str | None = None,
        extra_source: str | None = None,
    ) -> str:
        """Return a refined markdown body. The caller wraps it in a Skill."""
```

Returns the **body** only — name, description, version, etc. are
managed by the caller. (Why: refinement is about content improvement;
slug renames are out of scope.)

- `AnthropicProvider.refine` — `tool_use` on an `emit_refinement` tool
  whose input schema is `{"body": str}`. Tool choice forced. Cached
  system block.
- `ClaudeCodeProvider.refine` — JSON-only prompt; output is
  `{"body": "..."}`.

## Orchestrator

```python
def refine_skill(
    root: Path,
    slug: str,
    *,
    provider: LLMProvider,
    identity: Identity | None = None,
    hint: str | None = None,
    with_source: str | None = None,
) -> int:
    """Produce a new iteration. Returns the new version number."""
```

1. Strict-load the current skill via `read_skill(root, slug, identity=identity)`.
2. Load the latest `judged` event from `runs/*.jsonl` for this slug
   (reuses `promoter._latest_judge_score` — promote it to a public
   helper). If no judge run exists, raise `NoJudgmentToRefineError`
   ("refinement needs an error signal — run `forge judge {slug}` first").
3. Extract `JudgeFinding`s from the same audit event (the JSONL line
   carries `scores` but not findings — we'll need to also store
   findings in the audit event. **Spec change required**: extend
   `RunEvent` with optional `findings: list[JudgeFinding] = []` field,
   populate during `judge_skill`).
4. If `--with-source` is supplied, fetch it via the existing
   `extraction.fetcher.fetch` (license-aware, robots.txt) and produce
   a string for the prompt. Same source can be `file://` or `http(s)://`.
5. Call `provider.refine(skill, findings=..., hint=..., extra_source=...)`.
6. Determine the next version (max existing + 1).
7. Write the new iteration via `storage.write_iteration(...,
   kind="refined", created=today)`.
8. Add a `pending` Iteration to `lineage.yml`. `current_version`
   unchanged.
9. Append a `refined` `RunEvent` to `runs/*.jsonl`.
10. Print a unified diff (via `forge diff`'s helper) of `current → new`
    and the predicted improvements based on findings the refinement
    targeted.

## CLI

```
forge refine <slug>
       [--with-source URL|PATH]
       [--prompt TEXT]
       [--root PATH]
```

Exit codes: `0` ok, `1` fetch/IO failure, `2` not-yet-judged or
already-pending-iteration, `3` provider failure.

## Out of scope

- Multiple pending iterations. Refining when a pending iteration
  already exists raises with "accept or reject v{N} first".
- Auto-accept on score improvement (the whole point is human review).
- Refining a foreign-origin skill — federation problem.

## Out-of-band requirement: JudgeFinding persistence

Refinement needs findings, which judge currently returns but does not
persist (only the scores land in the JSONL audit + RunSummary).
This change extends:

- `RunEvent` gains `findings: list[JudgeFinding] = []`.
- `judge_skill` populates it.
- `_latest_judge_findings(root, slug)` helper returns `list[JudgeFinding]`.

Backward compat: old `RunEvent` lines without `findings` parse with
the default `[]`. Refinement on a skill judged before this change
fails-soft with "no findings on the latest judge run; rejudge".
