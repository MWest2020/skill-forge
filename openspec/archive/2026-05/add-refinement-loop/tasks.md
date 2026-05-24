# Tasks — add-refinement-loop

## Step 1 — models + iteration storage

- [x] `Iteration` model: version, kind, status, reject_reason, created, judge_score
- [x] `Lineage` model: slug, current_version, iterations[] (with monotonic + exactly-one-current invariants)
- [x] Storage helpers: `iterations_dir`, `write_iteration`, `read_iteration`, `read_lineage`, `write_lineage`
- [x] Iteration filename format: `v{N}-{kind}-{YYYY-MM-DD}.md`
- [x] `forge lineage migrate [--root PATH] [--slug SLUG] [--dry-run]` — converts flat to layout-with-iterations
- [x] Iterations store body-only (no frontmatter) so refine/accept can swap bodies cleanly
- [x] Tests: model round-trip, write/read iteration, lineage invariants, migration idempotency

## Step 2 — refine

- [x] Provider extension: `LLMProvider.refine(skill, *, findings, hint, extra_source) -> str`
- [x] `AnthropicProvider.refine` — forced tool_use on `emit_refinement` tool
- [x] `ClaudeCodeProvider.refine` — JSON-only `{"body": "..."}` prompt
- [x] `REFINEMENT_SYSTEM_PROMPT` carrying findings + hint + extra-source guidance
- [x] `RunEvent` gains `findings: list[JudgeFinding]` so refine can read them later
- [x] `refinement/refiner.py`: refine_skill orchestrator
- [x] `forge refine <slug> [--with-source URL|PATH] [--prompt TEXT]`
- [x] Refusal when no prior judge run, pending iteration exists, or no lineage yet
- [x] Tests: refines from findings, --prompt threads through, no-judgment-raises, pending-iteration-raises

## Step 3 — accept / reject / diff

- [x] `accept_iteration(root, slug, *, version, identity)` — promote iteration to current, re-sign
- [x] `reject_iteration(root, slug, *, version, reason)` — mark in lineage, files remain on disk
- [x] `forge refine-accept <slug> --iteration N`
- [x] `forge refine-reject <slug> --iteration N --reason TEXT`
- [x] `forge diff <slug> [--from vN] [--to vM]` — defaults from=to_v-1, to=highest iteration
- [x] Diff backend: `git diff --no-index` when available, else `difflib.unified_diff`
- [x] Tests: accept updates current + rewrites SKILL.md, reject preserves files but marks lineage, status-only-pending rules enforced

## Step 4 — validate + smoke + review

- [x] `ruff check`, `mypy --strict`, `pytest` green (200 tests)
- [x] **Live smoke** (real `claude -p`, end-to-end curation):
  - `forge import /tmp/initial-skill.md` → vague v1
  - `forge lineage migrate --slug debug-systemd-stuck-unit`
  - `forge judge` → 0.38 (1 blocker, 4 warnings)
  - `forge refine --prompt "add concrete commands"` → v2 pending
  - `forge diff` → clean body-only unified diff
  - `forge refine-accept --iteration 2` → v2 becomes current
  - `forge judge` again → 0.80 ("ready to promote")
- [x] `/review` ran, findings processed:
  - HIGH: `accept_iteration.model_copy` bypassed body validator → broken signature on leading-newline body → fixed via `Skill.model_validate({...})`
  - MEDIUM: `migrate_one` blind to partial state (lineage XOR iterations) → fixed via `PartialMigrationError`
  - MEDIUM: `git diff --color=always` ignored piped output → fixed via `sys.stdout.isatty()`
  - MEDIUM: `write_lineage` not atomic → fixed via write-tmp-then-rename
  - LOW: malformed run line silently swallowed → fixed via stderr warning
  - Reviewer finding #3 (promote moves SKILL.md but not lineage) was wrong — `shutil.move` moves the whole directory; verified in smoke.
  - Skipped: read-modify-write race (single-user, mtime check fragile); `cli.py` 706-line size (own refactor change).
- [x] `/security-review` ran — no qualifying findings ≥ 0.8 confidence
- [x] 5 regression tests added in `tests/test_review_fixes_c3.py`
- [x] Archive change folder, push
