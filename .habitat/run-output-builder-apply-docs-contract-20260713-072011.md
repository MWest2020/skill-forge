# Habitat builder — apply-docs-contract

_run_id builder-apply-docs-contract-20260713-072011 · verdict ok · 2026-07-13T07:22:38Z_

---

All file work is done. Task 4.1 (opening the PR) I'm leaving for the harness/Mark — task 1.1 states the habitat-harness manages branches and pushes, and my builder role forbids merging. I've prepared the PR body below.

## Run report — `apply-docs-contract`

**Scope:** implemented only this OpenSpec change. No changes to `CLAUDE.md`, `.claude/agents/`, or CI.

**What I did**
- Created `docs/` (minimum viable, per the repo-specific note — no prior `docs/` existed):
  - `docs/index.md` — one-paragraph what/status, link to README, links to present sections; references `STRATEGY.md` and `openspec/`.
  - `docs/reference/configuration.md` — one reference page distilled from README + `openspec/project.md` + `config/default.yml` (config keys, rubric axes, providers, CLI surface, known gap).
- Front matter on both pages: `status: draft` + `last_reviewed: 2026-07-13` (migration date), **no `owner` field** — these are distilled without a real content review, so `draft` per contract.
- `.mcp.json`: already present from the seed and conform template with the `TODO-change-3` placeholder — verified, no change needed.

**Decisions worth flagging**
- **No migration/stubs performed.** The only loose docs are `README.md` (contract says it stays) and `STRATEGY.md`. STRATEGY.md is cross-linked by relative path from README and `openspec/project.md`; moving it would break those links and exceed the "minimum viable" repo-specific scope. I left it in place and link to it from `docs/index.md` instead. If you'd rather have it migrated under `docs/explanation/` with a stub, that's a follow-up decision for you.

**Self-check (task 3.1) — passes**
- Markdown only in `index.md` + allowed submaps (`reference/`); no empty `how-to/`/`explanation/` dirs.
- Every page has YAML front matter.
- One language: English.

**Tasks:** 1.1, 2.1, 2.2, 2.3, 2.4, 3.1 checked off. 4.1 (open PR) left unchecked — I don't push or merge; that's harness/Mark territory.

**Ready-to-use PR body** (title: `docs: apply handbook docs contract`):

```markdown
Applies the handbook docs contract (Westmarch add-docs-contract) to skill-forge.

Contract points applied:
- [x] `docs/` structure per contract (index.md + reference/; empty dirs omitted)
- [x] Minimum viable: index.md + one reference page (CLI/pipeline configuration)
- [x] Front matter per page: status + last_reviewed; no owner field
- [x] Migrated-without-review pages: status: draft, last_reviewed = 2026-07-13
- [x] One language per repo: English
- [x] README kept; docs/index.md links to it, does not replace it
- [x] .mcp.json present per template (handbook URL placeholder TODO-change-3)
- [ ] No loose docs required migration (README stays; STRATEGY.md left in place — see note)

STOP: do not merge — Mark merges.
```

Nothing was pushed. Let me know if you want STRATEGY.md migrated too, or if I should attempt the `gh pr create` here.
