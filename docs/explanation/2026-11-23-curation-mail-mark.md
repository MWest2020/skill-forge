---
status: current
last_reviewed: 2026-11-23
---

# Curation decision 2026-11-23: mail-mark

Made for ratatoskr's chat agents (change `odin-mails-mark`). Mark, 2026-11-23:
*"en odin kan niet mailen net als jij, of weet niet hoe."* A role's tools are
derived from its skills (2026-10-22, see `2026-10-22-curation-read-state.md`),
so a chat agent that may mail needs a skill that declares the mail tools.

## Promoted (in this PR)

| Skill | Score | Decision |
|---|---|---|
| mail-mark | 0.92 | **live**. It teaches a chat agent to mail Mark, at `mark@westerweel.work` and nobody else, when he asks for it. `allowed-tools` adds `mcp__claude_ai_Gmail__send_message` and `mcp__claude_ai_Gmail__reply` and nothing else, and the handbook derives the role's tools from that. |

It was judged once, 3× with the per-axis median (rubric v2), with no warnings.
All axes scored 0.90 or higher.

## What the skill does not carry

The skill does not enforce the recipient. Ratatoskr enforces it with
`agents/mail_guard.py`, a PreToolUse hook on every chat turn that refuses any
Gmail call other than a send or reply to Mark alone. The skill says that the
hook exists and what its refusal looks like. A role that declares this skill
without that hook is not safe, so ratatoskr must be deployed before a role
gets the skill.

## The register

`register.yml` is regenerated: 48 live skills, with `mail-mark` the only new
entry. No other skill changes, so no other role's derived tools change.
