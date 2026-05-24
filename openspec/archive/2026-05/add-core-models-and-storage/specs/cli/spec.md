# Spec — CLI (`ls` and `show`)

Behavior for the two CLI commands enabled by this change. The other commands
stay on `NotImplementedError` until their respective changes land.

## `skill-forge ls`

Prints a table of all skills found by `storage.list_skills` using `rich.table`
(already a transitive dep of `typer`). Columns:

| Slug | Status | Score |
|---|---|---|
| `kubernetes-pvc-resize-on-statefulset` | live | 0.87 |
| `python-async-context-managers` | draft | 0.61 |

- "Score" shows `—` when `judge_score` is None.
- Output order: live first (alpha), then drafts (alpha).
- Exit code 0 when zero or more skills found. Empty repo just prints the empty
  header — does not fail.

## `skill-forge show <slug>`

Resolves the slug via `storage.read_skill`, prints in two sections:

```
## SKILL.md  (skills/<slug>/SKILL.md  |  draft)
---
<raw markdown body, including frontmatter as-rendered>
---

## sources.yml  (sources/<slug>.yml)
---
<raw YAML>
---
```

- Header line indicates path on disk and whether the skill is live or draft.
- If `sources/<slug>.yml` is missing, print a `[no provenance file]` placeholder
  rather than failing the command (sources are added later in the pipeline).
- Missing slug → exit code 1, error message naming both paths the storage layer
  tried.

## Argument shape

- `ls` takes no arguments.
- `show` takes one positional `slug`. No options.

These commands are the only CLI surface tested in this change. All others still
raise `NotImplementedError` and that is intentional — covered by an `xfail`
test that pins it.
