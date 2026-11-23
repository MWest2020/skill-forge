# Sync skips listener-only skills

## Why

A skill's `allowed-tools` are pre-approved by Claude Code wherever the skill is
installed. `mail-mark` declares `mcp__claude_ai_Gmail__send_message`, and that
tool is safe only inside a Ratatoskr chat turn, where the listener's mail guard
refuses every recipient but Mark. A plain `forge sync claude-code` mounts every
live skill into `~/.claude/skills`, so it would hand the coding session (and
every other Claude process of the user) a pre-approved mail tool with no guard.
Found by the security review of skill-forge#16.

## What changes

- **A tag, `listener-only`,** marks a skill that only its own consumer may load.
  `forge sync` never mounts such a skill into a target, whether the sync is for
  all skills or for one tag. A tagged sync that would only mount listener-only
  skills is an error.
- Ratatoskr is unaffected: its listener copies the skills its agents declare
  straight from `skills/` (`agents/agent_skills.py`), not through `forge sync`.
