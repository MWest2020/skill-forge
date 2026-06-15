# Spec — skillsets (`tags`)

## Data model

`Skill` gains:

```
tags: list[str] = []          # slug-shaped grouping labels; default empty
```

- Each tag matches the slug rule `[a-z0-9][a-z0-9-]*` (same validator as
  `name`); invalid tags fail model construction with a clear message.
- Tags are deduplicated and sorted on write, so the on-disk order is stable.
- `tags` is optional: a skill with no `tags` key parses to `[]` and round-trips
  back without emitting an empty `tags:` line.
- `tags` is independent of `origin`. `origin` records provenance (who/where);
  `tags` record purpose (what set). Neither derives from the other.

A **skillset** is not a stored object. It is the query *"every live skill whose
`tags` contain T"*. There is no skillset registry, id, or file.

## Storage query

`storage.live_skills_with_tag(root, tag) -> list[str]` returns the slugs of
**live** (promoted) skills whose `tags` include `tag`, sorted. Draft skills are
never included. Unknown tag → empty list (not an error).

## CLI

### `forge ls [--tag T]`

- Without `--tag`: unchanged (all skills, live + draft).
- With `--tag T`: list only skills carrying tag `T`. A new `Tags` column shows
  each skill's tags.

### `forge sync <target> [--tag T] [...existing flags]`

- Without `--tag`: unchanged (all live skills).
- With `--tag T`: mount only the skillset for `T` (live skills carrying `T`).
- `--tag` with `--unsync`: remove only that skillset's entries from the target
  manifest; entries from other tags stay.
- Empty skillset (no live skill carries `T`): exit 1 with
  `no live skills tagged 'T'` — never silently sync zero skills.

### `forge tags [--root PATH]`

Print each tag present across **live** skills with its skill count, sorted by
tag:

```
security   2
examenstof 5
```

No live tags: print `No tags on live skills.`

## Exit codes

- `0` — success (including an empty `ls --tag`, which is a valid empty list).
- `1` — `sync --tag` against an empty skillset.

## Non-goals

- No tag rename/merge command (edit frontmatter + re-judge instead).
- No tag hierarchy or namespacing — flat slugs only.
- No stored bundles; a skillset is always recomputed from a tag query.
