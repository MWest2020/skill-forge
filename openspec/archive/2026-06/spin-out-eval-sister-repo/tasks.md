# Tasks — spin out the eval sister-repo

> These are **trigger / kickoff** tasks, not implementation tasks for this repo.
> The documentation tasks (section 1) are done. The sister-repo tasks
> (section 2) are intentionally **unchecked** — they fire only when a trigger in
> `proposal.md` is hit, and they execute in the *new* repository, not here.

## 1. Record the boundary in skill-forge (done)

- [x] 1.1 STRATEGY.md — "When to spin out a sister-repo" section (`617ff70`)
- [x] 1.2 README — "Why (north star)" section names the sister-repo line (`f3047a3`)
- [x] 1.3 `project.md` — "North star" section names the sister-repo boundary (`c0783ca`)
- [x] 1.4 `no skill execution` non-goal points at this boundary
- [x] 1.5 File this proposal in the archive (not the active queue)

## 2. Kick off the sister-repo (deferred — do in the new repo, when triggered)

- [ ] 2.1 Confirm a trigger from `proposal.md` is actually hit (don't pre-build)
- [ ] 2.2 Create `skill-eval` / `agent-bench` with its own OpenSpec
- [ ] 2.3 Define its task-suite + run + outcome-stats data model (its own, not skill-forge's)
- [ ] 2.4 Build the runner that executes agents loaded with vetted skills
- [ ] 2.5 Consume vetted skills from skill-forge over the thin interface (sync / read `skills/`)
- [ ] 2.6 Emit effectiveness scores in a shape skill-forge can read

## 3. Close the loop back in skill-forge (deferred — future skill-forge change)

- [ ] 3.1 New skill-forge proposal: ingest effectiveness scores as one more judge input
- [ ] 3.2 Keep the interface thin — skills out, scores in; nothing more
