# Spec — Skill frontmatter additions

## New fields on `Skill`

| Field | Type | Default | Notes |
|---|---|---|---|
| `origin` | `str \| None` | `None` | `{instance_id}:{slug}:{version}` when set. Format validated via regex `^forge-[a-f0-9]{8}:[a-z0-9][a-z0-9-]*:\d+$` when not `None`. |
| `signature` | `str \| None` | `None` | Base64-encoded Ed25519 signature (88 chars including padding). Validated as ASCII base64 when not `None`. |

Both are `None` for backward compatibility — skills written before this
change still load. New skills written via `storage.write_skill` always get
both populated.

## Serialization order

Frontmatter YAML is rendered with `sort_keys=True` from this change forward.
Necessary so the canonical payload is reproducible across writes. The
visible order in `SKILL.md` becomes alphabetical:

```yaml
---
body: ...           # actually rendered separately; not in frontmatter
created: 2026-05-24
description: Use this skill when ...
judge_score: null
name: resize-statefulset-pvc
origin: forge-a1b2c3d4:resize-statefulset-pvc:1
signature: TFRSV...==
sources:
  - id: src-abc123
version: 1
---
```

(Note: `body` lives outside the frontmatter block — it's not affected.)

## Behavior of existing readers

`forge ls` and `forge show` continue to work for skills with `origin: null`
and `signature: null`. Neither field is required to display a skill.

## Migration

Skills authored before this change have `origin: None` / `signature: None`
in memory after `read_skill`. They are *not* migrated lazily — they stay
unsigned on disk until `forge identity backfill` stamps them. See
[`cli-identity/spec.md`](../cli-identity/spec.md).
