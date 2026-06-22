# Spin out the eval sister-repo

> **Status: direction proposal, not implemented work.** Unlike the other
> changes in this archive (which record completed work), this one records a
> *decision about where future work belongs* — namely, **not in this repo**.
> It is filed in the archive, not in `openspec/changes/`, on purpose: it is not
> an active change skill-forge will execute. The tasks below are the trigger
> checklist for the day it does become real, in a separate repository.

## Why

The north star is **the best possible agents**, and skill-forge is the
trust/quality layer over curated context artifacts that serves that goal (see
[`STRATEGY.md`](../../../STRATEGY.md), README "Why", `project.md` "North star").

The natural growth direction is trust shifting from **intrinsic** (does the
rubric think a skill looks good?) toward **extrinsic** (does the artifact
measurably make an agent better on a task?). Extrinsic measurement requires
*running agents against task suites* — which crosses skill-forge's hard
`no skill execution` non-goal.

Rather than let that pull execution, an eval framework, and a non-artifact data
model into skill-forge's curation core, the work belongs in a **sister-repo**
(working name `skill-eval` / `agent-bench`). This change records that boundary
so the decision is auditable and the trigger is recognizable when it arrives —
it does **not** authorize building anything here.

## What

**Recorded (no code change in skill-forge):**
- The sister-repo boundary is the existing `no skill execution` non-goal.
- The triggers (any one) that mean work has crossed into sister-repo territory:
  1. It needs to **execute** agents against task suites.
  2. It needs its own non-artifact data model/lifecycle (task suites, runs over
     time, outcome statistics).
  3. Adding it would force skill-forge's core to take a runtime / eval-framework
     dependency it otherwise wouldn't.
- The interface contract between the two repos (kept deliberately thin):
  - the eval repo **consumes** vetted skills from skill-forge (e.g. via `sync`
    or by reading the live `skills/` tree);
  - skill-forge **consumes** effectiveness scores back as *one more judge
    input* — extrinsic signal alongside the intrinsic rubric.
  - Two repos, one interface. They are not merged.

## Scope

- This repo: **documentation only** — STRATEGY.md "When to spin out a
  sister-repo" section, README "Why (north star)", `project.md` "North star".
  All already shipped (commits `617ff70`, `f3047a3`, `c0783ca`).
- The sister-repo itself: **out of scope here by definition.** Its models,
  task-suite format, runner, and eval harness are designed and built in that
  repository under its own OpenSpec, when started.

## Out of scope

- Building any eval / execution / benchmarking capability in skill-forge.
- Reopening the single-person curated-library scope (distribution/federation
  stay descoped per `strip-to-curation-core`).
- Choosing the sister-repo's name, stack, or harness — deferred to its kickoff.
- Wiring effectiveness scores into the judge — that is a *future* skill-forge
  change, gated on the sister-repo existing and producing scores; not now.

## Risks

- **The boundary erodes — eval logic creeps into skill-forge anyway.**
  Mitigated: the three triggers are explicit and the `no skill execution`
  non-goal now points at this proposal. Any PR that runs agents is a signal to
  start the sister-repo instead.
- **The sister-repo is built before curation/extrinsic trust is actually
  needed (YAGNI).** Mitigated: this is a *recognition* artifact, not a roadmap
  item. Nothing starts until intrinsic trust is proven insufficient in
  practice.
- **The interface grows fat (two repos become coupled).** Mitigated: the
  contract is two thin flows — skills out, effectiveness scores in. Anything
  beyond that warrants its own proposal.
