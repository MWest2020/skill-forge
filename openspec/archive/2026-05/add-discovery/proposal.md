# add-discovery

## Why

Until now, intake is manual (`forge import <path>`, `forge extract <url>`).
Discovery closes the gap: from a *topic* to a list of *candidate sources*
ready to extract. Per STRATEGY.md this is "useful, not central" — small,
bounded scope.

## What

- `forge discover <topic>` — search GitHub for matching repos/files, probe
  each candidate's license, print a candidate list with license badges.
  Forbidden licenses (none, unclear, paywall heuristics) are filtered out
  with a log entry to `discovery_blocked.log`.
- `forge run <topic>` — `discover` + top-N `extract` + `judge` in one
  command. `--max-candidates N` (default 3).
- GitHub search via `gh search` subprocess — reuses Mark's existing auth,
  no new keys or libs.
- License classification: GitHub API exposes `license` field on repos;
  for arbitrary URLs we fall back to an HTML heuristic (LICENSE link,
  footer text, `<meta name="license">`).

## Scope

- `src/skill_forge/discovery/{web,github,license_check}.py` (placeholders
  from change #1 filled in)
- `src/skill_forge/cli.py` — wire `discover` and `run`
- Tests with mocked `gh` subprocess + mocked HTTP for license probes
- A small `discovery_blocked.log` writer

## Out of scope

- Web search via Google/Bing/etc — adds a key. DuckDuckGo HTML scraping
  is fragile; skip until there's real need. GitHub-only for MVP.
- Auto-promotion of extracted skills. `run` stops at judge — user runs
  `forge promote` themselves.
- License classification beyond permissive / copyleft / restrictive /
  forbidden buckets.

## Risks

- **gh CLI binary missing on user's machine.** Mitigation: clear error
  message naming the install link.
- **GitHub rate limits.** `gh` uses the user's token; 5000 req/hr is
  plenty for personal use.
- **License heuristic false-negatives.** A genuinely permissive site
  without an obvious LICENSE link gets filtered out. Acceptable cost
  of caution — the user can still `forge extract <url>` directly.
