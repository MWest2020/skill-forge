# add-import-repo

## Why

`forge extract <url>` distills one page into one skill — useful when the
source IS one page (a blog post, a docs section). Repos like
`patricksavalle/investigate-journalism-skills` already contain a tree
of finished `SKILL.md` files; LLM-distilling the README gives back a
single pointer-skill instead of harvesting the individual real skills.

`forge import <path>` already imports a local SKILL.md. We need the
remote variant: walk a GitHub repo, find every `SKILL.md`, import each
one as it stands.

## What

- `forge import-repo <github-url> [--origin-tag TAG] [--root PATH]`
- Accepts `https://github.com/owner/repo` (default branch) or with an
  explicit `--ref BRANCH-OR-SHA`.
- Uses the existing `gh` CLI (already auth'd; reuses change #4's
  dependency) to walk the repo tree once via
  `gh api repos/{owner}/{repo}/git/trees/{ref}?recursive=1`.
- Filters tree entries whose path ends in `SKILL.md`.
- For each match, fetches the raw content via
  `gh api repos/{owner}/{repo}/contents/{path}?ref={ref}` and decodes
  the base64 `content` field.
- Tries to parse each as a `Skill` model. If it parses cleanly, lands
  it via the existing `import_file` flow (auto-suffix on slug
  collision, audit event, sources.yml). If it doesn't parse, logged
  to stderr and skipped.
- Source attribution: every imported skill gets a Source with
  `url=https://github.com/owner/repo/blob/{ref}/{path}`, `license`
  from the repo's GitHub-reported SPDX (reuses change #4's
  classify_spdx), and `contribution="imported from <owner>/<repo>"`.

## Scope

- `src/skill_forge/import_skill/repo.py` with `import_github_repo`
- CLI: `forge import-repo` command
- Reuses: existing `gh` subprocess wrapper pattern, `import_file`
  internals, `classify_spdx`
- Tests with mocked `gh` subprocess + a real-looking tree payload

## Out of scope

- Non-GitHub git hosts (GitLab, Codeberg, self-hosted). Same pattern
  works but each needs its own client; defer until there's demand.
- Auto-rewriting external skills with LLM distillation when their
  frontmatter doesn't match our schema. Skip + log is enough for MVP.
  Users can `forge extract <raw-url>` individual ones if they want.
- Following submodules.
- Recursive imports through symlinked SKILL.md files.

## Risks

- **GitHub API rate-limit for unauthenticated runs.** Mitigation:
  the `gh api` subprocess uses the user's token, which has 5000/hr.
  Tree walks are one call per repo, raw fetches are one per skill —
  realistic repos have <100 skills.
- **A repo with hundreds of SKILL.md is hostile.** Mitigation: cap
  at 50 imports per command (`--max-skills` overridable).
- **Skill name collisions inside the same repo.** Two SKILL.md files
  with frontmatter `name: foo` would clobber each other. Auto-suffix
  via `free_slug` handles it (foo, foo-2, ...).
