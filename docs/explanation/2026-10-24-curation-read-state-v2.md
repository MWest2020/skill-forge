---
status: current
last_reviewed: 2026-10-24
---

# Curation decision 2026-10-24: read-state v2

`read-state` (promoted 2026-10-22, see
`2026-10-22-curation-read-state.md`) goes to version 2: it teaches the read
shell's seventh lookup, `comments <repo> <issue> [k]` (ratatoskr #172), and
when to use it.

## Why

On 2026-10-24 the wordsworth build `pilot-ingest-manifest` was failed twice by
its reviewer, both times on real findings. Both times odin could not see the
finding: the roles' verdicts are comments on the build issue, and the read
shell had no way to read them. So odin held the day's last build and asked
Mark to paste the verdict. A skill that says "read the state before you
speak" has to cover the place where the state is written.

## What changed

- The command list has the `comments` line.
- "When to use it" has a third case: after a failed build, read the role's
  finding before choosing between a rebuild, an amend and asking Mark.
- The description names "an issue's comments".
- Version 2, re-signed by this instance (`forge-996cce1c:read-state:2`,
  verifies); `register.yml` regenerated. The tools are unchanged
  (`Bash(python3 agents/readshell.py:*)`), so no role's derived tools change.

## Not done

**Not re-judged.** The change adds one command and one usage case in the
existing form; the v1 score (0.92) is not carried over as a claim about v2.
Judge it in the next curation round.

**Process slip.** PR #13 was merged with this docs-drift gate failing: the
merge script did not stop on a failing check. This document is the fix
forward. The rule stays: merge only when every check passes.
