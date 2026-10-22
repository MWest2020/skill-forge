---
allowed-tools:
- Bash(python3 agents/readshell.py:*)
created: '2026-10-22'
description: Look up the live state of the work on Mark's GitHub repositories (commits,
  branches, open OpenSpec changes, PRs, issues, a PR's checks) through ratatoskr's
  read shell instead of guessing or asking. Use before saying what is open, blocked,
  merged or failing.
judge_score: null
name: read-state
origin: forge-996cce1c:read-state:1
signature: CUrYBWfZVKkNilNVzCvyaFXWMkjXra10LcI+n98dYKaY4/mh3Rtng8SItC0t3tIcawJHQA4jbs8sqdN2XEsJAw==
sources:
- id: src-d26804
  url: https://github.com/MWest2020/ratatoskr/blob/main/docs/how-to/read-shell.md
tags:
- ratatoskr
- read-only
version: 1
visibility: private
---

# Read the state of the work

You have one Bash command, and only this one: ratatoskr's read shell. It answers
six read-only questions about a repository of `MWest2020`. Give the repository
name only (`wordsworth`, not `MWest2020/wordsworth`).

    python3 agents/readshell.py log <repo> [n]        # last n commits on main (default 15)
    python3 agents/readshell.py branches <repo>
    python3 agents/readshell.py changes <repo>        # open OpenSpec changes
    python3 agents/readshell.py prs <repo> [n]        # open pull requests
    python3 agents/readshell.py issues <repo> [label] # open issues, e.g. label agent-work
    python3 agents/readshell.py checks <repo> <pr>    # the checks of one PR

The command runs from your working directory, which is the ratatoskr listener's
tree, so `agents/readshell.py` is right as written. If the answer is "No such
file", say that the read shell is unavailable and do not guess the state.

## When to use it

- **Before you state what the work looks like.** That covers what is open,
  what waits on Mark, and whether a PR is green. Look it up; do not answer
  from memory or from what someone said in the channel.
- **When a build or a merge is mentioned.** Read the issue or the PR's checks
  rather than assuming the outcome.

## Example

Mark asks: *"is the wordsworth PR green?"*

1. `python3 agents/readshell.py prs wordsworth` lists `#212 habitat/builder/…
   — build: fix-x`.
2. `python3 agents/readshell.py checks wordsworth 212` gives one line per
   check: `verify  pass`, `gates / gates  pending`.
3. Answer with the check names exactly as they came back: "PR #212 is not
   green yet: `verify` passed, `gates / gates` is still pending."

Pick the question by what it is about: a change that is decided but not yet
built is `changes`, work in review is `prs`, and work someone asked for is
`issues`.

## How to read the answers

- `(none: …)` means the lookup worked and the list is empty. That is a real
  answer.
- `failed: HTTP 404` means the repository or path does not exist. `changes` on
  a repository without OpenSpec does this.
- Output is capped at 40 lines and says how many it dropped. Ask a narrower
  question (`issues <repo> <label>`, `log <repo> 5`) instead of guessing about
  the rest.

## What it cannot do

It reads and changes nothing: no comments, labels, merges or pushes. Anything
else in Bash is refused: pipes, `;`, `$(...)`, other programs and absolute
paths. Run the command exactly in the form above, one call per question.

## Source

https://github.com/MWest2020/ratatoskr/blob/main/docs/how-to/read-shell.md
