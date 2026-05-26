# add-subscribe-and-cite

## Why

Two threads in one change:

1. **Source citation in bodies.** `sources/{slug}.yml` carries `src-XXXXXX`
   IDs and URLs, but the SKILL.md body itself doesn't cite where the
   content came from. A reader (or agent) opening just the file has no
   way back. Audit-defensible content always cites; we currently flunk
   that quietly. Fix in the extraction + refinement prompts.

2. **Subscribe / follow / check-updates.** Once a skill is distilled
   from a source, we want to know when the source changes. No DB
   needed — `sources/{slug}.yml` already records `sha256`. A small
   `subscriptions.yml` tracks which sources are watched + the
   `last_sha256` we've seen. `forge check-updates` re-fetches and
   reports diffs. Bonus: `--refine` auto-triggers `forge refine` with
   the new source content (still a pending iteration, user accepts).

## What

### Source citation

- Extraction prompts (Anthropic, Claude Code, Ollama) now mandate a
  final `## Source` section in the body containing the URL (and page
  title if discernible). The required body sections become:
  - `## When to use`
  - `## Procedure`
  - `## Failure modes`
  - `## Source` (new, mandatory)
- Refinement prompts now preserve the `## Source` section. If absent
  on input, the refinement is required to add it from
  `sources/{slug}.yml`.
- Judge rubric's `provenance_quality` axis is rewritten to penalise
  the *absence* of a body-level `## Source` section, not just opaque
  source IDs. The same axis still rewards meaningful `sources.yml`.

### Subscribe

- `subscriptions.yml` at repo root:
  ```yaml
  subscriptions:
    - slug: foo
      url: https://example.com/article
      last_sha256: abc...
      last_checked: 2026-05-26T18:00:00Z
  ```
- `forge subscribe <slug>` — read `sources/{slug}.yml`, pick the first
  Source whose URL is http(s)://, add it to `subscriptions.yml` with
  the current `last_sha256` populated from the source. Refuses if
  the source URL is `local-author:...` or `federation:...` (those
  aren't refetchable).
- `forge subscribe --list [--root PATH]` — table of watched URLs +
  last_checked timestamp.
- `forge subscribe --remove <slug>` — drop entry.
- `forge check-updates [--root PATH] [--refine]` — re-fetches every
  watched URL, compares sha256 against `last_sha256`. Reports
  `unchanged` / `changed` / `unreachable`. With `--refine`, on
  `changed` for a skill that's been judged: trigger `refine_skill`
  with `extra_source` = the new content. New iteration lands pending.

### Audit

- `RunEvent.event` gains `"subscribed"` and `"checked"`.
- `checked` events carry `metadata.changed: true|false` and
  `metadata.url`.

## Scope

- `src/skill_forge/subscribe/{__init__,subscriptions.py,check.py}`
- `models.RunEvent` event vocabulary extended
- `models.Skill` no schema change (body cite is in the prose, not
  a structured field)
- `providers/_prompts.py` — extraction + refinement + judge prompts
  updated for source citation
- `providers/_judge.py` — judge prompt clarifies the new bar
- `cli.py` — `forge subscribe` sub-typer + `forge check-updates`
- Tests: subscriptions CRUD, check-updates with mocked HTTP, prompt
  consistency (new test: every extract prompt mentions `## Source`)
- Update the cross-prompt consistency test to require "Source"
  appears in every extraction and refinement prompt

## Out of scope

- Daemon / watch mode for `check-updates`. Cron is enough.
- `forge subscribe <peer> <slug>` for federation peers — same idea
  applies but the implementation is different (peer's manifest +
  `judge_score` diff). Deferred.
- Surfacing subscription state in `forge ls`. Could add a column
  later if the use case justifies it.

## Risks

- **Bodies created before this change lack `## Source`.** Mitigation:
  judge will start flagging them via the rewritten rubric. User can
  `forge refine` to add the section. Don't backfill automatically —
  refinement is human-reviewed by design.
- **check-updates re-fetches over robots.txt.** Same gates as the
  existing fetcher; sources that were once accessible may become
  blocked. Treat that as `unreachable` and continue.
- **Sha256 changes on cosmetic source edits** (whitespace, ad reload).
  Mitigation: out-of-scope normalisation. The user sees the diff and
  decides whether to refine.
