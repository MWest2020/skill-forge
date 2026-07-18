# Add --source-url to forge import

## Why

`forge import <path>` records every file as `url: local-author:<instance>`
with `license: unknown` — factually wrong for externally-authored work that
happens to arrive via a local path (cloned repo, download). Hit twice in
practice: the ai-literacy-superpowers cherry-pick (2026-07-18) needed a manual
patch of frontmatter url + `## Source` + re-sign before the judge's
`provenance_quality` axis went from 0.20–0.30 (blocker) to 0.75–0.90.
`import-repo` already does this right; single-file import lacks the input.

## What

- `forge import <path> --source-url <url> [--license <spdx>]`:
  - `source_url` flows to `normalize_skill_md` → injected frontmatter
    sources-ref carries the url and the body gets a `## Source` section
    (same behavior as repo imports).
  - The provenance `Source` record uses the given url (instead of
    `local-author:`) and the given license (instead of `unknown`).
- Omitting the flags keeps today's behavior byte-for-byte (true local
  authorship stays `local-author:`).
- `import-dir` is untouched: one URL cannot describe a directory of skills.

## Out of scope

- Injecting a url into a *pre-existing* frontmatter `sources` field — the
  normalizer only stamps the ref it creates (matches import-repo).
- License validation/classification — the value is recorded, not verified.
- Fetching the URL to compare hashes.

## Risks

- Wrong URL supplied by the operator: recorded as-is; sha256 of the local
  bytes still anchors what was actually imported.
