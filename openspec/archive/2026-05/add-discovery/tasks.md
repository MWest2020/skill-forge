# Tasks — add-discovery

- [x] `discovery/github.py`: search_repos via `gh search repos --json`
- [x] `discovery/license_check.py`: classify_spdx + classify_html
- [x] GitHub license shortcuts: SPDX → bucket map (incl. -only/-or-later suffixes, MPL-1.1, EPL, CDDL after review)
- [x] HTML heuristic for non-GitHub URLs (SPDX-in-body regex)
- [x] `forge discover <topic> [--limit N]` rich table + license badges
- [x] `forge run <topic> [--max-candidates N]` discover → extract loop
- [x] `discovery_blocked.log` writer (JSONL after review feedback)
- [x] Tests: 23 (gh mocked, classify parametrized, CLI smoke, JSONL log)
- [x] Live smoke: real `gh search "kubernetes pvc resize"` returned 1 candidate, classified forbidden, logged.
- [x] `/review` — applied: SPDX variants expanded, classify_html simplified, JSONL log, exit-code-2 re-raise, web.py stub deleted, dead `LLMProviderError` re-export dropped
- [x] `/security-review` — clean, no findings
