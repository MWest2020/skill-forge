# Tasks — add-discovery

- [ ] `discovery/github.py`: `search_repos(topic, *, limit=10) -> list[str]` via `gh search repos --json fullName,htmlUrl,licenseInfo`
- [ ] `discovery/license_check.py`: `classify(url, *, http_client) -> str` returning permissive | copyleft | restrictive | forbidden
- [ ] GitHub license shortcuts: SPDX → bucket map
- [ ] HTML heuristic for non-GitHub URLs: look for `<link rel="license">`, footer text
- [ ] `discovery/web.py`: stub returning `[]` (out of scope for MVP) — keeps the interface intact
- [ ] `forge discover <topic> [--limit N]` prints candidate list with license badges
- [ ] `forge run <topic> [--max-candidates N]` runs discover → top-N extract → judge each
- [ ] `discovery_blocked.log` writer for forbidden-license skips
- [ ] Tests: gh subprocess mocked, license classifier with table-driven cases, CLI smoke
- [ ] `/review` + `/security-review`, fixes, archive
