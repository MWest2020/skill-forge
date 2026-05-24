# Tasks — add-refinement-loop

## Step 1 — models + iteration storage

- [ ] `Iteration` model: `version: int`, `kind: Literal["imported","extracted","refined","accepted"]`, `created: date`, `judge_score: float | None`
- [ ] `Lineage` model: `slug: str`, `current_version: int`, `iterations: list[Iteration]`
- [ ] Storage helpers: `write_iteration(root, slug, *, body, version, kind, identity)`, `read_lineage`, `write_lineage`, `iterations_dir(root, slug)`
- [ ] Iteration filename format: `v{N}-{kind}-{YYYY-MM-DD}.md` (e.g. `v1-imported-2026-05-24.md`)
- [ ] `forge lineage migrate [--root PATH] [--dry-run]` — converts flat skills to layout-with-iterations (creates v1, writes lineage.yml, leaves SKILL.md as a copy of v1)
- [ ] Tests: model round-trip, write/read iteration, lineage versioning, migration is idempotent

## Step 2 — refine

- [ ] Provider extension: `LLMProvider.refine(skill, *, findings, hint, extra_source) -> RefinementResult` returning the refined body
- [ ] `AnthropicProvider.refine` — tool_use forcing on `emit_refinement` tool
- [ ] `ClaudeCodeProvider.refine` — JSON-only prompt
- [ ] Refinement prompt template carrying findings + hint
- [ ] `refinement/refiner.py`: `refine_skill(root, slug, *, provider, identity, with_source, hint)` — loads skill + latest findings → calls provider → writes new iteration (not promoted; lineage updated)
- [ ] Refinement requires the skill to have been judged at least once (loads latest findings from runs/*.jsonl)
- [ ] `forge refine <slug> [--with-source URL|PATH] [--prompt TEXT] [--root PATH]`
- [ ] Tests: refines from findings, --prompt threads through, --with-source folds in new content, refusal when no prior judge run

## Step 3 — accept / reject / diff

- [ ] `accept_iteration(root, slug, *, version, identity)` — promote that iteration to be the current SKILL.md, re-sign
- [ ] `reject_iteration(root, slug, *, version, reason)` — mark in lineage, files remain on disk
- [ ] `forge refine-accept <slug> --iteration N`
- [ ] `forge refine-reject <slug> --iteration N --reason TEXT`
- [ ] `forge diff <slug> [--from vN] [--to vM]` — defaults from=current-1, to=current. Shells to `git diff --no-index`; falls back to `difflib.unified_diff` if `git` missing.
- [ ] Tests: accept updates current_version + rewrites SKILL.md, reject leaves files but marks lineage, diff with both backends

## Step 4 — validate + smoke + review

- [ ] `ruff check`, `mypy --strict`, `pytest` clean
- [ ] **Live smoke**:
  - Migrate existing demo skill (creates v1)
  - `forge judge <slug>` → score with findings
  - `forge refine <slug>` → v2 lands in iterations/ via real `claude -p`
  - `forge diff <slug>` → shows unified diff v1 → v2
  - `forge refine-accept <slug> --iteration 2` → SKILL.md updated, current=2 in lineage.yml
  - Re-judge to confirm the refinement actually improved the score
  - `forge refine-reject` round-trips on a third iteration
- [ ] `/review` on the diff
- [ ] `/security-review` on the diff
- [ ] Apply findings (commit separately)
- [ ] Archive change folder, push
