# add-refinement-loop

## Why

This is the change that makes skill-forge a curation tool instead of yet another extraction pipeline. Once a skill has been judged (change #2) we know what is weak about it — but the existing roadmap had no path to fix those weaknesses other than re-writing by hand. Refinement closes the loop: judge findings + optional new source → an improved draft, stored alongside the old one with lineage intact.

The differentiator versus every marketplace and registry surveyed in `STRATEGY.md` lives here. Marketplaces ship `latest`; refinement ships `iteratively better, with the trail`.

## What

### Refine a skill

A new `forge refine <slug>` command and a `refine` subroutine. Inputs:

- The skill (must exist; must have been judged at least once — refinement without an error signal is not supported in v1).
- The latest judge findings (auto-loaded from the most recent `Run` for the slug).
- Optional `--with-source <url-or-path>` — a new source whose content should be folded into the refinement. Goes through the same license check + sha256 capture as `import`.
- Optional `--prompt <inline text>` — a user-provided hint, e.g., "tighten the procedure, drop the historical context".

Output:

- A refined SKILL.md written to a **new iteration directory** under the slug, not overwriting the live or draft skill.
- A diff (unified) printed to stdout, plus optionally saved.
- The `lineage.yml` file updated with the new iteration entry.
- A `refined` event in `runs/{run_id}.jsonl`.

### Iteration storage

The on-disk shape changes from:

```
skills/{slug}/SKILL.md
```

to:

```
skills/{slug}/SKILL.md           # the current promoted version
skills/{slug}/lineage.yml        # iteration history
skills/{slug}/iterations/
    v1-imported-2026-05-24.md    # historical iterations, never deleted
    v2-refined-2026-05-26.md
    v3-refined-2026-05-27.md     # if this is current, SKILL.md is identical to it
```

(`SKILL.md` always equals the highest-version file in `iterations/`. The duplication is intentional: consumers reading `skills/{slug}/SKILL.md` should not need to understand `iterations/`.)

The same applies to draft skills: `skills/_draft/{slug}/iterations/v1-...md` etc.

### Apply or reject

After refinement produces a new iteration, the user explicitly accepts or rejects it:

- `forge refine-accept <slug> --iteration <n>` — promotes iteration `n` to become the new `SKILL.md` (and updates `lineage.yml`'s `current` pointer). Re-judges and re-signs.
- `forge refine-reject <slug> --iteration <n> [--reason REASON]` — marks the iteration as rejected in `lineage.yml`. Files stay on disk for audit; the current pointer is unchanged.

If the user does nothing, the new iteration sits in `iterations/` indefinitely. It is not silently activated.

### Diff and review

`forge diff <slug> [--from v2] [--to v3]` shows a unified diff between two iterations of a skill. Defaults: `from=current-1`, `to=current`.

This is the primary review affordance. The CLI does not ship its own diff implementation; it shells out to `git diff --no-index` if available, falls back to Python's `difflib.unified_diff` if not.

## Scope

- New CLI: `refine`, `refine-accept`, `refine-reject`, `diff`.
- New module `src/skill_forge/refinement/` with `refine_skill`, `accept_iteration`, `reject_iteration`.
- New `Lineage` and `Iteration` models.
- Storage layer additions: `iterations/` directory writing, `lineage.yml` read/write, migration shim that creates a `v1` iteration for skills that pre-date this change.
- Provider extension: `LLMProvider.refine(skill, findings, hint, extra_source) -> RefinementResult`.
- A migration command `forge lineage migrate` that turns existing flat skills into the new layout (move the existing `SKILL.md` to `iterations/v1-imported-<date>.md`, write a minimal `lineage.yml`, leave `SKILL.md` in place as a copy of v1).

## Out of scope

- Auto-refinement (judge-then-refine in one step). Tempting, but human review of each iteration is the whole point. Bulk operations subvert that.
- Cross-skill refinement (merge two skills into one). Conceptually clean, operationally messy — defer.
- Branching iterations. Each lineage is linear: v1 → v2 → v3. If you want a fork, copy the skill to a new slug.
- A web UI for diffing iterations.
- Reverting `SKILL.md` to an old iteration via something other than `refine-accept`. There is one promotion mechanism.
- Federation of iteration history. Federation (change #8) ships the current iteration plus `lineage.yml` summary; full iteration bodies are local-only by default.

## Risks

- **Iterations bloat the repo.** Mitigation: each iteration is one markdown file. 100 iterations is ~100 KB. Acceptable for years. A `forge lineage prune <slug> --keep-last N` command can land later if it matters.
- **LLM refinement makes the skill worse.** Mitigation: refinements are non-destructive; the user has to opt in via `refine-accept`. The CLI shows the diff and the predicted new judge score; the user decides.
- **`lineage.yml` becomes the source of truth, divergent from the filesystem.** Mitigation: lineage is the *index*, filesystem is the *truth*. `forge lineage verify <slug>` cross-checks; called automatically before any accept/reject.
- **Migration touches every existing skill.** Mitigation: migration is explicit (`forge lineage migrate`), prints a plan, requires confirmation. Idempotent.
- **Refinement prompts encode opinion about what "better" means.** Mitigation: the rubric and findings drive the prompt; the model is asked to address specific findings, not to globally "improve". Tested with adversarial findings ("make it shorter" + "add more detail" → graceful failure, not hallucinated reconciliation).
