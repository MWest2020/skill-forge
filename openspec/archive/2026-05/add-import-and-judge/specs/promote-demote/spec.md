# Spec — promote and demote

Lives at `src/skill_forge/promotion/promoter.py`.

## API

```python
def promote(
    root: Path,
    slug: str,
    *,
    promotion: dict,                # {"total_min": float, "axis_min": float}
    force: bool = False,
    identity: Identity | None = None,
) -> Path: ...                      # returns the new live SKILL.md path

def demote(
    root: Path,
    slug: str,
    *,
    reason: str,
    identity: Identity | None = None,
) -> Path: ...                      # returns the new draft SKILL.md path
```

## Behavior

### `promote(root, slug, *, promotion, force, identity)`

1. Verify the draft exists at `skills/_draft/{slug}/SKILL.md`. If only
   `skills/{slug}/SKILL.md` exists (already live), raise
   `AlreadyPromotedError`.
2. Load the skill via `storage.read_skill(root, slug, identity=identity)`.
   Strict-load applies — tampered drafts can't be promoted silently.
3. Load the latest `RunSummary` from `sources/{slug}.yml`. If none exists
   AND `force is False`, raise `NotJudgedError("run `forge judge {slug}`
   first or pass --force")`.
4. Threshold check (skipped when `force=True`):
   - `judge_score >= promotion["total_min"]`
   - every per-axis score from the latest judge run >= `promotion["axis_min"]`
   - if either fails, raise `BelowThresholdError` with the specific axis(es).
5. Move `skills/_draft/{slug}/` → `skills/{slug}/` via `Path.rename`.
   (`sources/{slug}.yml` stays put — provenance is path-independent.)
6. Append a `Run` event (`event="promoted"`, `promoted=True`,
   `topic=None`) to `runs/{run_id}.jsonl`.
7. Return the new live path.

### `demote(root, slug, *, reason, identity)`

1. Verify the live skill exists at `skills/{slug}/SKILL.md`. Raise
   `NotLiveError` otherwise.
2. Strict-load via `read_skill` (same protection as promote).
3. Move `skills/{slug}/` → `skills/_draft/{slug}/`. If the draft path
   already exists (a refinement landed in draft while the old version was
   live), raise `DemoteCollisionError` — caller decides whether to force.
4. Append a `Run` event (`event="demoted"`, `promoted=False`,
   `metadata={"reason": reason}`) to `runs/{run_id}.jsonl`.
5. Return the new draft path.

## CLI

```
forge promote <slug> [--force] [--root PATH]
forge demote  <slug> --reason TEXT [--root PATH]
```

- `forge promote` exit codes: `0` promoted, `1` below threshold or
  collision, `2` not judged (suggest `forge judge` first or `--force`),
  `3` identity / signature issue.
- `forge demote --reason` is required (non-empty). Empty reason → exit `1`.

## Out of scope

- Promote-from-iteration (change #3 `add-refinement-loop` adds
  `forge refine-accept` for that).
- Bulk promote/demote.
- Auto-demote on judge regression.
