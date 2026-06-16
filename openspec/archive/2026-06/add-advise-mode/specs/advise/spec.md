# Spec — `forge advise`

## Signature

```
forge advise <target> [--runs N] [--root PATH]
```

- `target`: either an imported **slug** (`[a-z0-9][a-z0-9-]*`, resolved under
  `skills/` then `skills/_draft/`) or a **filesystem path** to a `SKILL.md`
  (contains `/` or `.md`, or names an existing file). Path wins if the file
  exists; otherwise treated as a slug.
- `--runs N`: override `judge.runs` for this call (default from config). `>= 1`.
- `--root PATH`: project root. Defaults to cwd.

## Behavior

1. Resolve the target to a `Skill`:
   - **slug** → `storage.read_skill(root, slug)` (no identity; read-only).
   - **path** → read the file; if it carries skill-forge frontmatter, parse
     directly; if it's a vanilla skill (`name` + `description` only), normalize
     in memory via the shared normalizer (inject `version`/`created`/`sources`,
     strip foreign fields) — exactly as `import-repo` does, but **never
     written**.
2. Score it with the read-only `score_skill` (median-of-N, same as the gate).
   **No** `runs/` event, **no** `sources.yml` write, **no** promotion.
3. Print structured advice:

   ```
   Advice: <slug-or-filename>
     schema_compliance    0.85  ✓
     clarity              0.95  ✓
     ...
     ────────────────────────────
     total                0.88  ✓  (threshold 0.75)

   Strengths:
     - clarity, actionability  (clear, no findings)
   Weaknesses & fixes:
     [warning] provenance_quality: <finding observation>
     [info] gap_coverage: <finding observation>

   Verdict: would promote.   (or: below threshold — N axis/axes under 0.50)
   ```

   Strengths = axes `>= axis_min` with no finding. Weaknesses & fixes = the
   judge findings (which name what lost points). Verdict mirrors the promote
   gate (`total >= total_min` AND every axis `>= axis_min`) but **only states**
   it — never acts.

## Exit codes

- `0` — advice produced (regardless of whether it would promote; advising a
  weak skill is a successful lint, not an error).
- `1` — target not found (no such slug and no such file), or the path's content
  can't be parsed/normalized into a skill.
- `2` — `--runs < 1`.
- `3` — provider error (same as judge).

## Guarantees

- **Read-only.** `advise` calls `score_skill` (which performs no I/O) and a
  formatter. It never writes under `skills/`, `sources/`, or `runs/`. A test
  asserts the tree is unchanged after an `advise` run.
- **Same score as the gate.** `advise` and `judge` share `score_skill`, so for
  an imported skill at the same `--runs` they produce the same per-axis median
  (modulo model non-determinism) — advise is a preview of the gate, not a
  second opinion.

## Non-goals

- No writes, no promotion, no audit record (use `judge` to record a score).
- No rubric changes; no separate "suggestion" LLM call.
