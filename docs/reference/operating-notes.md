---
status: current
last_reviewed: 2026-09-24
---

# Operating notes

Things the code does not tell you, learned while running the curation loop.

## Judging and tiers

- **Old judge events turn invisible after a rubric bump.** v1 (5-axis) events
  fail v2 (8-axis) validation, `audit.latest_event` skips them, and the skill
  shows `untiered` (`forge gold` says "not judged") while `ls` still shows the
  stale score from `sources/<slug>.yml`. Re-judge under the current rubric.
- **Parallel judging can fail silently.** In one run, 5 of 19 re-judges under
  6-way parallel `forge judge` produced no event; a sequential retry worked
  every time. After a batch, check that each slug has a new judge event
  (`forge judge <slug> --explain`) — exit 0 is not proof.
- **Silver needs a calibration dated after the judge run.** Re-judging drops a
  skill to bronze until you run `forge calibrate` again.
- `refine` on a ~150-line skill needs `claude_code.timeout_s: 300` (set it in
  the gitignored `config/local.yml`); `forge calibrate` exits 3 on a timeout.

## Signing and gold

- To re-sign after editing live skill content, set `signature: None` before
  `fs.write_skill(..., identity=...)` — `_stamp` only signs when the field is
  missing. `get_or_create()` takes the identity **home**
  (`~/.config/skill-forge`), not `.../identity`; the wrong path mints a stray
  keypair and every skill silently skips signing.
- Gold attests `skill_origin` + `version`, not the content signature: editing
  a gold skill's frontmatter does not lapse gold. The gold private key is only
  needed for a new gold or a re-attest after a version bump. `forge gold` warns
  when it would mint a new gold identity; a new identity forks the trust chain,
  so restore the key instead (it lost one once, from `/tmp`).

## Curation decisions not visible in git

Drafts, sources and runs are gitignored, so a dropped import leaves no commit.
From the anthropics/skills import (2026-07-12):

- **template-skill** — dropped: gap coverage median 0.45, below the axis floor
  (well written, but a content-free template).
- **theme-factory** — dropped: a schema blocker, and its value lived in bundled
  asset files the import did not bring.

Do not re-import them without a new reason.

## Usage

A global `PreToolUse` hook on the `Skill` tool (in `~/.claude/settings.json`,
not in this repo) appends `{ts, slug, cwd, session}` to `usage/usage.jsonl`
(gitignored). Counts: `jq -r .slug usage/usage.jsonl | sort | uniq -c`.
Whether a skill actually *helps* is still unmeasured.
