---
status: current
last_reviewed: 2026-11-23
---

# Curation decision 2026-11-23: mail-mark

Made for ratatoskr's chat agents (change `odin-mails-mark`). Mark, 2026-11-23:
*"en odin kan niet mailen net als jij, of weet niet hoe."* A role's tools are
derived from its skills (2026-10-22, see `2026-10-22-curation-read-state.md`),
so a chat agent that may mail needs a skill that declares the mail tool.

## Promoted (in this PR)

| Skill | Score | Decision |
|---|---|---|
| mail-mark | 0.92 | **live**, version 2. It teaches a Ratatoskr chat agent to mail Mark, at `mark@westerweel.work` and nobody else, when he asks for it. `allowed-tools` adds `mcp__claude_ai_Gmail__send_message` and nothing else. The handbook derives the role's tools from that. |

## Version 2, after the security review of this PR

Version 1 (0.92) also declared `mcp__claude_ai_Gmail__reply`. The review found
two problems with it:

- **The reply tool is gone.** The connector's reply may copy a thread's
  default cc recipients, which no guard can see in the call. A mail in a
  thread is the same `send_message` with `replyThreadId`.
- **The skill never reaches a user's own skills directory.** A skill's
  allowed tools are pre-approved wherever it is installed, and the tool is
  safe only inside a Ratatoskr chat turn, where ratatoskr's mail guard runs.
  So the skill:
  - says this in its text, and how to tell that it is in such a turn;
  - carries the new tag `listener-only`, which `forge sync` never mounts
    (change `sync-skips-listener-only`, in this PR);
  - keeps `visibility: private`.

  Ratatoskr's listener copies skills from `skills/` directly, not through
  sync, and refuses to install a skill whose allowed tools hold a sending
  connector tool other than this one.

Version 2 was re-signed by this instance (`forge-996cce1c:mail-mark:2`,
verifies). It was then judged four times, 3× each with the per-axis median
(rubric v2). Each round's one warning was fixed before the next:

1. **0.92**: one warning, no concrete signal for "a Ratatoskr chat turn" and
   no handling of connector errors.
2. **0.93**: one warning, no way to tell that a request came from Mark. It now
   points at the listener's `mark:` line, which comes from the sender's
   verified key.
3. **0.93**: one warning, `replyThreadId` should be the default, and "say in
   the channel" needed explaining.
4. **0.92**, with no warnings.

## What the skill does not carry

The skill does not enforce the recipient. Ratatoskr enforces it with
`agents/mail_guard.py`, a PreToolUse hook on every chat turn. The hook refuses
any Gmail call other than a send to Mark alone. Settings files cannot switch it
off, and it blocks the call when it cannot run. A role that declares this skill
without that hook is not safe, so ratatoskr must be deployed before a role gets
the skill.

## The register

`register.yml` is regenerated: 48 live skills. `mail-mark` is the only new
entry, with one tool. No other skill changes, so no other role's derived tools
change.
