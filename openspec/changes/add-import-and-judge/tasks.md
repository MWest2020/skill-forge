# Tasks — add-import-and-judge

## Step 1 — import

- [ ] `src/skill_forge/import_skill/__init__.py` + `import_skill/importer.py`
- [ ] `import_file(root, path, *, origin_tag, identity)` — parses, validates, writes draft + sources.yml
- [ ] `import_directory(root, dir, *, origin_tag, identity)` — finds subdirs with `SKILL.md`, imports each
- [ ] Invalid frontmatter → reject before writing anything (no partial state)
- [ ] Source provenance: declared `source` URL when present in frontmatter, else single Source with `url=local-author:{instance_id}`
- [ ] `forge import <path> [--origin-tag TAG] [--root PATH]`
- [ ] `forge import-dir <dir> [--origin-tag TAG] [--root PATH]`
- [ ] Tests: happy path, invalid frontmatter rejection, bulk import skips non-skill dirs, --origin-tag annotates Source.contribution

## Step 2 — judge

- [ ] `JudgeFinding` model: axis, observation, severity (`info`/`warning`/`blocker`)
- [ ] Provider extension: `LLMProvider.judge(skill) -> tuple[JudgeScore, list[JudgeFinding]]`
- [ ] `AnthropicProvider.judge` — tool_use forcing on a `score_skill` tool
- [ ] `ClaudeCodeProvider.judge` — JSON-only prompt with score + findings
- [ ] Judge prompt template in `providers/_prompts.py` carrying the rubric weights
- [ ] `src/skill_forge/evaluation/judge.py` filled in — orchestrates provider call + audit-log write
- [ ] `forge judge <slug>` — runs judge, prints score breakdown + findings, updates `sources/{slug}.yml` runs list
- [ ] Tests: happy path with mocked providers (both), bad provider output handling, JudgeFinding validation

## Step 3 — audit trail

- [ ] `src/skill_forge/audit.py` (or fold into storage) — `append_run(root, run)` writes one JSONL line to `runs/{run_id}.jsonl`
- [ ] `Run` model gains an `event` field: `imported` / `judged` / `promoted` / `demoted` (or split into RunEvent)
- [ ] Each command (import, judge, promote, demote) appends one Run line
- [ ] `RunSummary` written into `sources/{slug}.yml` whenever a judge produces a score
- [ ] `runs/` stays gitignored; documented in README
- [ ] Tests: append is atomic-ish (write then rename, or stdlib write+flush+fsync), JSON shape stable

## Step 4 — promote / demote

- [ ] `src/skill_forge/promotion/promoter.py` filled in
- [ ] `promote(root, slug, *, force=False)` — loads latest `RunSummary`, checks threshold (total >= total_min AND every axis >= axis_min)
- [ ] Move SKILL.md from `skills/_draft/{slug}/` to `skills/{slug}/` (sources.yml stays put)
- [ ] `demote(root, slug, *, reason)` — move back to draft, log reason in audit trail
- [ ] `forge promote <slug> [--force]` and `forge demote <slug> --reason TEXT`
- [ ] Tests: promotion succeeds at threshold, fails below threshold, --force overrides, demote round-trips

## Step 5 — validate + smoke + review

- [ ] `ruff check`, `mypy --strict`, `pytest` all green
- [ ] **Live smoke** end-to-end:
  - Write a small fixture SKILL.md
  - `forge import <fixture>` → draft lands, sources.yml written, audit line in runs/
  - `forge judge <slug>` → real `claude -p` call returns score + findings, sources.yml updated
  - `forge promote <slug>` → at-threshold goes live, below-threshold refuses
  - `forge demote <slug> --reason "test"` → back to draft, reason logged
- [ ] `/review` on the change-#2 diff
- [ ] `/security-review` on the change-#2 diff
- [ ] Apply findings (commit separately)
- [ ] Archive change folder, push
