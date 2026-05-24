# Tasks — add-import-and-judge

## Step 1 — import

- [x] `src/skill_forge/import_skill/__init__.py` + `import_skill/importer.py`
- [x] `import_file(root, path, *, origin_tag, identity)` — parses, validates, writes draft + sources.yml
- [x] `import_directory(root, dir, *, origin_tag, identity)` — finds subdirs with `SKILL.md`, imports each
- [x] Invalid frontmatter → reject before writing anything (no partial state)
- [x] Source provenance: `url=local-author:{instance_id}` for our skills, `url=external:{origin}` for foreign
- [x] `forge import <path> [--origin-tag TAG] [--root PATH]`
- [x] `forge import-dir <dir> [--origin-tag TAG] [--root PATH]`
- [x] Tests: happy path, invalid frontmatter rejection, bulk import skips non-skill dirs, --origin-tag annotates Source.contribution, foreign-origin preserved, audit event appended, bulk shares one run_id

## Step 2 — judge

- [x] `JudgeFinding` model: axis, observation, severity (`info`/`warning`/`blocker`)
- [x] Provider extension: `LLMProvider.judge(skill, *, weights) -> tuple[JudgeScore, list[JudgeFinding]]`
- [x] `AnthropicProvider.judge` — `tool_use` forcing on a `score_skill` tool with cache_control
- [x] `ClaudeCodeProvider.judge` — JSON-only prompt to `claude -p` with score + findings
- [x] Judge prompt template in `providers/_prompts.py` carrying rubric axes + severity vocabulary
- [x] Total computed client-side from per-axis × weights (no model/weight drift)
- [x] `src/skill_forge/evaluation/judge.py` orchestrator — strict-load + provider call + audit log + RunSummary
- [x] `forge judge <slug>` — runs judge, prints score breakdown + findings, updates `sources/{slug}.yml` runs list
- [x] RunSummary capped at the latest 20 per skill
- [x] Tests: happy path with mocked providers (both), bad provider output handling, JudgeFinding validation, audit event written

## Step 3 — audit trail

- [x] `src/skill_forge/audit.py` — `append_run_event(root, event)` writes one JSONL line
- [x] `RunEvent` model: run_id, event, timestamp, skill_slug, scores?, promoted, metadata
- [x] `next_run_id(root)` — scans existing `runs/*.jsonl`, returns next `run-YYYY-MM-DD-NNN`
- [x] Each command (import, judge, promote, demote) appends one Run line
- [x] `RunSummary` written into `sources/{slug}.yml` whenever a judge produces a score
- [x] `runs/` stays gitignored (already in `.gitignore` from change #1 baseline)
- [x] Tests: append creates directory, appends to existing file, run_id increments, ignores bad filenames

## Step 4 — promote / demote

- [x] `src/skill_forge/promotion/promoter.py` filled in
- [x] `promote(root, slug, *, promotion, force, identity)` — checks `total_min` AND `axis_min` per-axis
- [x] Per-axis check reads the latest "judged" event from `runs/*.jsonl` (full JudgeScore lives there)
- [x] Move SKILL.md from `skills/_draft/{slug}/` to `skills/{slug}/` via `shutil.move`
- [x] `demote(root, slug, *, reason, identity)` — back to draft, reason in audit metadata
- [x] `forge promote <slug> [--force]` and `forge demote <slug> --reason TEXT`
- [x] Tests: promotion at threshold, below threshold blocked, --force overrides, demote round-trips, axis_min check blocks skewed score, demote requires non-empty reason

## Step 5 — review + fixes

- [x] `ruff check` clean
- [x] `mypy --strict` clean
- [x] `pytest` green (162 tests)
- [x] **Live smoke** end-to-end via real `claude -p`:
  - `forge import /tmp/incoming-skill.md` → draft + sources + audit line
  - `forge judge enable-linux-zswap` → 0.87 total, 2 specific findings
  - `forge promote enable-linux-zswap` → live, audit logged
  - `forge demote --reason "test"` → back to draft, reason in metadata
  - All four events in `runs/run-2026-05-24-001..004.jsonl`
- [x] `/review` ran, findings processed:
  - HIGH: axis_min check (data was already in JSONL audit) → fixed via `_latest_judge_score` helper
  - MEDIUM: `_latest_run_score(...) or skill.judge_score` masks legitimate 0.0 → fixed with `is not None`
  - MEDIUM: `import_file` double-read race → fixed via `parse_skill_text` (read once, parse from string)
  - LOW: brittle `len(run_files) == 1` test → loosened to `>= 1` with content search
  - Skipped: `next_run_id` atomicity (single-user, theoretical), `promote` double-check (defensive, not dead), `cli.py` 484-line size (own refactor change), `_judge_stub` dedup (cosmetic)
- [x] `/security-review` ran — no qualifying findings ≥ 0.8 confidence
- [x] Also fixed (security-review bonus): `_scan` + `_latest_run_score` now catch `yaml.YAMLError` — was a real `forge ls` crash on hand-edited bad YAML
- [x] Archive change folder, push
