# Tasks — add-subscribe-and-cite

## Source citation (mandatory `## Source` section)

- [x] Extraction prompt (Anthropic _prompts.py) — adds `## Source` required section
- [x] Extraction prompt (Claude Code) — same
- [x] Extraction prompt (Ollama) — same
- [x] Refinement prompt (Anthropic) — preserves/adds `## Source`
- [x] Refinement prompt (Claude Code) — same
- [x] Refinement prompt (Ollama) — same
- [x] Judge prompt (Anthropic + Claude Code + Ollama) — `provenance_quality` now
  hard-penalises missing `## Source` (score ≤ 0.4)
- [x] Cross-prompt consistency test still passes (every axis + severity present)
- [x] Live smoke: re-extracted `patricksavalle/investigate-journalism-skills`
  → body ends with `## Source\n- [Title](URL) — desc`

## Subscribe + check-updates

- [x] `subscribe/subscriptions.py`: Subscription + SubscriptionsFile + CRUD
- [x] `subscribe/check.py`: check_updates — re-fetch, compare sha256, update manifest
- [x] `RunEvent.event` accepts `"checked"`
- [x] CLI: `forge subscribe <slug>` / `forge subscribe --list` /
  `forge subscribe <slug> --remove` / `forge check-updates`
- [x] Refuses non-http(s) sources (local-author, federation)
- [x] Audit: every check produces a `checked` RunEvent with `status` metadata
- [x] Tests: 12 (model validation, CRUD, check_updates with mocked fetch
  including unchanged/changed/unreachable, audit append, CLI 4 paths)
- [x] Live smoke: subscribed real URL, check-updates ran end-to-end

## Known limitation

- For dynamic HTML pages (GitHub repo views, news sites with session
  tokens), the raw-bytes sha256 compare will almost always report
  "changed" because the HTML body shifts between fetches even when
  content is identical. Documented; follow-up change can add an
  HTML→text normalization step before hashing, or honor
  ETag/Last-Modified headers.
