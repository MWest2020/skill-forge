# Spec — models

Pydantic v2 models, strict mode (no extra fields, no implicit coercion of
unrelated types).

## `Skill`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | `str` | yes | Slug-shaped: `^[a-z0-9][a-z0-9-]*$`. Used as folder name. |
| `description` | `str` | yes | One-paragraph "when to use this skill" hint. |
| `version` | `int` | yes | Schema version, starts at 1. |
| `sources` | `list[SourceRef]` | yes (≥1) | `SourceRef` = `{id: str}`; full Source lives in `sources/{slug}.yml`. |
| `judge_score` | `float \| None` | no | Last total score, 0.0–1.0. None means not yet judged. |
| `created` | `date` | yes | First time this skill was promoted (or drafted). |
| `body` | `str` | yes | Markdown body **excluding** frontmatter. |

Validation:

- `name` must match the slug regex; reject anything else with a clear error.
- `sources` must be non-empty.
- `judge_score`, when present, must be in `[0.0, 1.0]`.
- Round-trip: `Skill(**skill.model_dump()) == skill`.

## `Source`

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | `str` | yes | `src-` + 6 hex chars, e.g. `src-a1b2c3`. |
| `url` | `str` | yes | Absolute URL (http/https/file). |
| `license` | `str` | yes | SPDX identifier when known (e.g. `Apache-2.0`), else free-form. |
| `fetched_at` | `datetime` | yes | UTC timestamp of the fetch. |
| `sha256` | `str` | yes | 64-char lowercase hex digest of the fetched content. |
| `contribution` | `str` | yes | One sentence: what this source contributed to the skill. |

Validation:

- `id` matches `^src-[a-f0-9]{6}$`.
- `sha256` matches `^[a-f0-9]{64}$`.
- `fetched_at` is timezone-aware.

## `JudgeScore`

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_compliance` | `float` | yes | 0.0–1.0 |
| `clarity` | `float` | yes | 0.0–1.0 |
| `actionability` | `float` | yes | 0.0–1.0 |
| `gap_coverage` | `float` | yes | 0.0–1.0 |
| `provenance_quality` | `float` | yes | 0.0–1.0 |
| `total` | `float` | yes | Weighted sum per `config/default.yml`. |

Validation:

- Every axis in `[0.0, 1.0]`.
- `total` recomputed from the axes + weights must equal the stored `total`
  (tolerance 1e-9). Reject otherwise — guards against silent drift.

## `Run`

| Field | Type | Required | Notes |
|---|---|---|---|
| `run_id` | `str` | yes | `run-YYYY-MM-DD-NNN` (zero-padded daily counter). |
| `started_at` | `datetime` | yes | UTC. |
| `finished_at` | `datetime \| None` | no | Set when the run completes. |
| `topic` | `str \| None` | no | None for single-source runs (`extract <url>`). |
| `skill_slug` | `str` | yes | The slug being produced/updated. |
| `scores` | `JudgeScore \| None` | no | Populated by the judge stage. |
| `promoted` | `bool` | yes | True if promoted to live during this run. |
